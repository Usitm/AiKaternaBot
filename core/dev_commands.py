from discord.ext import commands
from core.utils.chat_formatting import box, pagify
from core import checks
import asyncio
import discord
import traceback
import inspect
import textwrap
from contextlib import redirect_stdout
import io


class Dev:
    def __init__(self, bot):
        self.bot = bot
        self._last_result = None
        self.sessions = set()

    @staticmethod
    def cleanup_code(content):
        """Automatically removes code blocks from the code."""
        # remove ```py\n```
        if content.startswith('```') and content.endswith('```'):
            return '\n'.join(content.split('\n')[1:-1])

        # remove `foo`
        return content.strip('` \n')

    @staticmethod
    def get_syntax_error(e):
        if e.text is None:
            return '```py\n{0.__class__.__name__}: {0}\n```'.format(e)
        return '```py\n{0.text}{1:>{0.offset}}\n{2}: {0}```'.format(e, '^', type(e).__name__)

    @staticmethod
    def sanitize_output(ctx: commands.Context, input: str) -> str:
        token = ctx.bot.http.token
        r = "[EXPUNGED]"
        result = input.replace(token, r)
        result = result.replace(token.lower(), r)
        result = result.replace(token.upper(), r)
        return result

    @commands.command()
    async def debug(self, ctx, *, code):
        """
        Executes code and prints the result to discord.
        """
        env = {
            'bot': self.bot,
            'ctx': ctx,
            'channel': ctx.channel,
            'author': ctx.author,
            'server': ctx.guild,
            'message': ctx.message
        }

        code = self.cleanup_code(code)

        try:
            result = eval(code, env, locals())
        except SyntaxError as e:
            await ctx.send(self.get_syntax_error(e))
            return
        except Exception as e:
            await ctx.send('```py\n{}: {}```'.format(type(e).__name__, str(e)), )
            return

        if asyncio.iscoroutine(result):
            result = await result

        result = str(result)

        result = self.sanitize_output(ctx, result)

        await ctx.send(box(result, lang="py"))

    @commands.command(name='eval')
    @checks.is_owner()
    async def _eval(self, ctx, *, body: str):
        """
        Executes code as if it was the body of an async function
            code MUST be in a code block using three ticks and
            there MUST be a newline after the first set and
            before the last set. This function will ONLY output
            the return value of the function code AND anything
            that is output to stdout (e.g. using a print()
            statement).
        """
        env = {
            'bot': self.bot,
            'ctx': ctx,
            'channel': ctx.channel,
            'author': ctx.author,
            'server': ctx.guild,
            'message': ctx.message,
            '_': self._last_result
        }

        env.update(globals())

        body = self.cleanup_code(body)
        stdout = io.StringIO()

        to_compile = 'async def func():\n%s' % textwrap.indent(body, '  ')

        try:
            exec(to_compile, env)
        except SyntaxError as e:
            return await ctx.send(self.get_syntax_error(e))

        func = env['func']
        try:
            with redirect_stdout(stdout):
                ret = await func()
        except:
            value = stdout.getvalue()
            await ctx.send(box('\n{}{}'.format(value, traceback.format_exc()), lang="py"))
        else:
            value = stdout.getvalue()
            try:
                await self.bot.add_reaction(ctx.message, '\u2705')
            except:
                pass

            if ret is None:
                if value:
                    await ctx.send(box(value, lang="py"))
            else:
                ret = self.sanitize_output(ctx, ret)
                self._last_result = ret
                await ctx.send(box("{}{}".format(value, ret), lang="py"))

    @commands.command()
    @checks.is_owner()
    async def repl(self, ctx):
        """
        Opens an interactive REPL.
        """
        variables = {
            'ctx': ctx,
            'bot': self.bot,
            'message': ctx.message,
            'server': ctx.guild,
            'channel': ctx.channel,
            'author': ctx.author,
            '_': None,
        }

        if ctx.channel.id in self.sessions:
            await ctx.send('Already running a REPL session in this channel. Exit it with `quit`.')
            return

        self.sessions.add(ctx.channel.id)
        await ctx.send('Enter code to execute or evaluate. `exit()` or `quit` to exit.')

        def msg_check(m):
            return m.author == ctx.author and m.channel == ctx.channel and \
                m.content.startswith('`')

        while True:
            response = await self.bot.wait_for(
                "message",
                check=msg_check)

            cleaned = self.cleanup_code(response.content)

            if cleaned in ('quit', 'exit', 'exit()'):
                await ctx.send('Exiting.')
                self.sessions.remove(ctx.channel.id)
                return

            executor = exec
            if cleaned.count('\n') == 0:
                # single statement, potentially 'eval'
                try:
                    code = compile(cleaned, '<repl session>', 'eval')
                except SyntaxError:
                    pass
                else:
                    executor = eval

            if executor is exec:
                try:
                    code = compile(cleaned, '<repl session>', 'exec')
                except SyntaxError as e:
                    await ctx.send(self.get_syntax_error(e))
                    continue

            variables['message'] = response

            stdout = io.StringIO()

            msg = None

            try:
                with redirect_stdout(stdout):
                    result = executor(code, variables)
                    if inspect.isawaitable(result):
                        result = await result
                    result = self.sanitize_output(ctx, result)
            except:
                value = stdout.getvalue()
                value = self.sanitize_output(ctx, value)
                msg = "{}{}".format(value, traceback.format_exc())
            else:
                value = stdout.getvalue()
                if result is not None:
                    msg = "{}{}".format(value, result)
                    variables['_'] = result
                elif value:
                    msg = "{}".format(value)

            try:
                for page in pagify(msg, shorten_by=12):
                    await ctx.send(box(page, "py"))
            except discord.Forbidden:
                pass
            except discord.HTTPException as e:
                await ctx.send('Unexpected error: `{}`'.format(e))

    @commands.command()
    @checks.is_owner()
    async def mock(self, ctx, user: discord.Member, *, command):
        """Runs a command as if it was issued by a different user

        The prefix must not be entered"""
        # Since we have stateful objects now this might be pretty bad
        # Sorry Danny
        old_author = ctx.author
        old_content = ctx.message.content
        ctx.message.author = user
        ctx.message.content = ctx.prefix + command

        await ctx.bot.process_commands(ctx.message)

        ctx.message.author = old_author
        ctx.message.content = old_content
