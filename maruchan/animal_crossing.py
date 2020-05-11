import logging
import json

import discord
from discord.ext.commands.view import StringView
from discord.ext import commands
from datetime import datetime, timedelta, timezone

from pymongo import MongoClient, ReturnDocument

from selenium import webdriver
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities

import io

DATE_MSG = (
    "lunes", 
    "martes", 
    "miercoles", 
    "jueves", 
    "viernes", 
    "sabado", 
    "domingo")

TIME_MSG = (
    "am", 
    "pm")

PATTERN_MSG = (
    "ls", 
    "f", 
    "d", 
    "ss",
    "n")

CLT = timezone(timedelta(hours=-4))

logger = logging.getLogger("root")


class AnimalCrossing(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self._client = MongoClient(
            'mongo',
            username='root',
            password='password')

        self._db = self._client.get_database("animal_crossing")

    def show_info(self, ctx: commands.Context, tags):
        logger.debug("AC:")
        logger.debug("  author: " + str(ctx.author))
        logger.debug("  channel: " + str(ctx.channel))
        logger.debug("  guild: " + str(ctx.guild))
        logger.debug("  me: " + str(ctx.me))

        for i in range(len(tags)):
            logger.debug("   arg[" + str(i) + "]: " + tags[i])

    async def send_chart_png(self, ctx: commands.Context, args: str):
        chart_img = None
        try:
            driver = webdriver.Remote(
                "http://selenium-firefox:4444/wd/hub", 
                DesiredCapabilities.FIREFOX)
            driver.set_window_size(1024, 768)
            driver.get("http://turnipprophet:8000/" + args)
            chart = driver.find_element_by_id("chart")
            chart_img = chart.screenshot_as_png
            driver.close()

        except Exception as e:
            logger.error("Error generating plot:" + str(e))
            chart_img = None

        if chart_img is not None:
            try:
                await ctx.send(
                    "`(*＾▽＾)／` :", 
                    file=discord.File(io.BytesIO(chart_img), 'plot.png'))
            except Exception as e:
                logger.error("Error sending plot:" + str(e))
                chart_img = None

        return chart_img

    async def get_data(
            self, 
            ctx: commands.Context, 
            target: discord.Member, 
            year: int, week: int,
            timeout_ms: int = 0):
        logger.debug("get_data:")
        logger.debug("  target: " + str(target))
        logger.debug("  date: " + str(year) + " " + str(week))

        week_data = self._db["stalk_market"].find_one({
            "user": str(target),
            "year": year,
            "week": week
        })

        del week_data["_id"]
        logger.debug("  result: " + str(week_data))

        if week_data is not None:
            msg = await ctx.send("```" + json.dumps(
                week_data, sort_keys=True, indent=2) + "```")
            if timeout_ms > 0 and msg is not None:
                await msg.delete(delay=timeout_ms/1000)

    async def get_all_data(
            self, 
            ctx: commands.Context, 
            year: int, week: int,
            timeout_ms: int = 0):
        logger.debug("get_all_data:")
        logger.debug("  date: " + str(year) + " " + str(week))

        all_week_data = self._db["stalk_market"].find({
            "year": year,
            "week": week
        })

        for week_data in all_week_data:
            del week_data["_id"]
            logger.debug("  result: " + str(week_data))

            if week_data is not None:
                msg = await ctx.send("```" + json.dumps(
                    week_data, sort_keys=True, indent=2) + "```")
                if timeout_ms > 0 and msg is not None:
                    await msg.delete(delay=timeout_ms/1000)

    async def get_plot(
            self, 
            ctx: commands.Context, 
            target: discord.Member, 
            year: int, week: int):
        logger.debug("get_plot:")
        logger.debug("  target: " + str(target))
        logger.debug("  date: " + str(year) + " " + str(week))

        week_data = self._db["stalk_market"].find_one({
            "user": str(target),
            "year": year,
            "week": week
        })

        if week_data is None:
            await ctx.send(
                "No hay datos para graficar `˚‧º·(˚ ˃̣̣̥᷄⌓˂̣̣̥᷅ )‧º·˚`")
            return

        plot_link = "".join((
            "https://turnipprophet.io",
            self.gen_plot_args(week_data)))

        await ctx.send(
            "`o(*ﾟ▽ﾟ*)o` el grafico de " + target.display_name + ": " + plot_link)
        await self.send_chart_png(ctx, self.gen_plot_args(week_data))

    async def get_all_plots(
            self, 
            ctx: commands.Context, 
            year: int, week: int):
        logger.debug("get_plot:")
        logger.debug("  date: " + str(year) + " " + str(week))

        all_week_data = self._db["stalk_market"].find({
            "year": year,
            "week": week
        })

        i = 0
        for week_data in all_week_data:
            plot_link = "".join((
                "https://turnipprophet.io",
                self.gen_plot_args(week_data)))
            members = [
                member for member in ctx.guild.members if (
                    str(member) == week_data["user"])]
            
            if len(members) != 1:
                continue

            target = members[0]
            await ctx.send(
                "`o(*ﾟ▽ﾟ*)o` el grafico de " + target.display_name + ": " + plot_link)
            i+=1

        if i == 0:
            await ctx.send(
                "No hay datos para graficar `˚‧º·(˚ ˃̣̣̥᷄⌓˂̣̣̥᷅ )‧º·˚`")
            return


    def gen_plot_args(self, week_data):
        pattern = week_data.get("lwp", "")
        return "".join((
            "?prices=%s.%s.%s.%s.%s.%s.%s.%s.%s.%s.%s.%s.%s" % (
                str(week_data["data"].get("d0-0", "")), 
                str(week_data["data"].get("d1-0", "")), 
                str(week_data["data"].get("d1-1", "")), 
                str(week_data["data"].get("d2-0", "")), 
                str(week_data["data"].get("d2-1", "")), 
                str(week_data["data"].get("d3-0", "")), 
                str(week_data["data"].get("d3-1", "")), 
                str(week_data["data"].get("d4-0", "")), 
                str(week_data["data"].get("d4-1", "")), 
                str(week_data["data"].get("d5-0", "")), 
                str(week_data["data"].get("d5-1", "")), 
                str(week_data["data"].get("d6-0", "")), 
                str(week_data["data"].get("d6-1", ""))), 
                "&pattern=0" if pattern == "F" else (
                    "&pattern=1" if pattern == "LS" else (
                        "&pattern=2" if pattern == "D" else (
                            "&pattern=3" if pattern == "SS" else (
                                ""
                            )
                        )
                    )
                )
            ))

    async def update_data(
            self, 
            ctx: commands.Context, 
            target: discord.Member, 
            year: int, week: int, day: int, time: int,
            cant: int):

        logger.debug("update_data:")
        logger.debug("  target: " + str(target))
        logger.debug("  date: " + str(year) + " " + str(week))
        logger.debug("  time: " + str(day) + " " + str(time))
        logger.debug("  cant: " + str(cant))

        week_data = self._db["stalk_market"].find_one({
            "user": str(target),
            "year": year,
            "week": week
        })
        
        if week_data is None:
            if cant <= 0:
                ctx.send("`˓˓(ᑊᘩᑊ⁎)`")
                return
            logger.debug("  creating!")
            self._db["stalk_market"].insert({
                "user": str(target),
                "year": year,
                "week": week,
                "data": {
                    "d" + str(day) + "-" + str(time) : cant
                }
            })
            week_data = self._db["stalk_market"].find_one({
                "user": str(target),
                "year": year,
                "week": week
            })
        else:
            logger.debug("  updating!")
            if cant <= 0:
                week_data = self._db["stalk_market"].find_one_and_update(
                    {
                        "user": str(target),
                        "year": year,
                        "week": week
                    },
                    {"$unset": {
                        "data.d" + str(day) + "-" + str(time): ""}},
                    return_document=ReturnDocument.AFTER)
                if len(week_data["data"].keys()) == 0:
                    self._db["stalk_market"].find_one_and_delete(
                    {
                        "user": str(target),
                        "year": year,
                        "week": week
                    })
                    await ctx.send("`Σ(゜ロ゜;)` ya no hay datos")
                    return
            else:
                week_data = self._db["stalk_market"].find_one_and_update(
                    {
                        "user": str(target),
                        "year": year,
                        "week": week
                    },
                    {"$set": {"data.d" + str(day) + "-" + str(time): cant}},
                    return_document=ReturnDocument.AFTER)

        del week_data["_id"]

        await ctx.send("`(*＾▽＾)／` recibido")
        await self.get_data(ctx, target, year, week, 10000)

    async def set_last_pattern(
            self, 
            ctx: commands.Context, 
            target: discord.Member, 
            year: int, week: int, pattern: str):

        logger.debug("set_last_pattern:")
        logger.debug("  target: " + str(target))
        logger.debug("  date: " + str(year) + " " + str(week))
        logger.debug("  pattern: " + pattern.upper())

        week_data = self._db["stalk_market"].find_one({
            "user": str(target),
            "year": year,
            "week": week
        })
        
        if week_data is None:
            logger.debug("  creating!")
            self._db["stalk_market"].insert_one(
                {
                    "user": str(target),
                    "year": year,
                    "week": week,
                    "data": {},
                    "lwp": pattern.upper()
                })
            week_data = self._db["stalk_market"].find_one({
                "user": str(target),
                "year": year,
                "week": week
            })
        else:
            logger.debug("  updating!")
            if pattern.upper() == "N":
                week_data = self._db["stalk_market"].find_one_and_update(
                    {
                        "user": str(target),
                        "year": year,
                        "week": week
                    },
                    {"$unset": {"lwp": ""}},
                    return_document=ReturnDocument.AFTER)

                if len(week_data["data"].keys()) == 0:
                    self._db["stalk_market"].find_one_and_delete(
                    {
                        "user": str(target),
                        "year": year,
                        "week": week
                    })
                    await ctx.send("`Σ(゜ロ゜;)` ya no hay datos")
                    return
            else:
                week_data = self._db["stalk_market"].find_one_and_update(
                    {
                        "user": str(target),
                        "year": year,
                        "week": week
                    },
                    {"$set": {"lwp": pattern.upper()}},
                    return_document=ReturnDocument.AFTER)

        del week_data["_id"]

        await ctx.send("`(*＾▽＾)／` recibido")
        await self.get_data(ctx, target, year, week, 10000)

    def get_target(
            self, ctx: commands.Context, member_info, default_result=None):
        logger.debug("get_target:")
        logger.debug("  info:" + str(member_info))
        targets = [
            member for member in ctx.guild.members if (
                member_info.lower() in member.display_name.lower()
                ) or (
                    str(member.id) in member_info)]
        targets = [target for target in targets if "Villano" in [
            str(role) for role in target.roles]]

        if(len(targets) != 1):
            # couldnt find target
            logger.debug("  GAAHH " + str(
                [str(target) for target in targets]))
            return default_result

        logger.debug("  found: " + str(targets[0]))
        return targets[0]
    
    def get_date(self, timestamp: datetime):
        logger.debug("get_date:")
        logger.debug("  timestamp: " + str(timestamp.isoformat()))
        iso_week = timestamp.isocalendar()

        save_year = iso_week[0] if iso_week[2] < 7 else (
            timestamp + timedelta(days=7)).isocalendar()[0]
        save_week = iso_week[1] if iso_week[2] < 7 else (
            timestamp + timedelta(days=7)).isocalendar()[1]

        save_day = iso_week[2] if iso_week[2] < 7 else 0
        save_time = 0 if timestamp.hour < 12 or save_day == 0 else 1

        logger.debug(
            "  result: " + str((save_year, save_week, save_day, save_time)))
        return (save_year, save_week, save_day, save_time)

    def parse_timestamp(self, possible_ts:str):
        ts = None
        try:
            ts = datetime.strptime(possible_ts, "%Y-%m-%d")
        except ValueError:
            try:
                ts = datetime.strptime(possible_ts, "%m-%d")
                ts = ts.replace(year=datetime.today().year)
            except ValueError:
                ts = None
        return ts


    @commands.command(aliases=['Ac', 'aC', 'ac'])
    async def AC(self, ctx: commands.Context, *, stock_command: str):
        """Animal Crossing."""
        tags = []
        view = StringView(stock_command)
        while not view.eof:
            tag = view.get_word()
            tags.append(tag)
            view.skip_ws()

        self.show_info(ctx, tags)

        if len(tags) == 0:
            await ctx.send("`(●´ω｀●)ゞ`")
            return

        target = ctx.author
        timestamp = ctx.message.created_at.replace(
            tzinfo=timezone.utc).astimezone(CLT)

        if "Villano" not in [str(role) for role in target.roles]:
            await ctx.send("`(⁎˃ᆺ˂)` no eres un villano")
            return

        if tags[0].lower() == "plot":
            tag = tags.pop(0)
            while len(tags) > 0:
                tag = tags.pop(0)
                ts = self.parse_timestamp(tag)

                if ts is not None:
                    timestamp = ts
                else:
                    target = self.get_target(ctx, tag, None)
                    if target is None:
                        await ctx.send(
                            "`｡(*^▽^*)ゞ` no entendi... q es '" + str(
                                tag) + "' ?")
                        return

            (save_year, save_week, _, _) = self.get_date(timestamp)
            await self.get_plot(ctx, target, save_year, save_week)
            return

        if tags[0].lower() == "plot_all":
            if str(target) != "Grillo#6124":
                await ctx.send(
                    "`┬┴┬┴┤(･_├┬┴┬┴` no quiero")
                return
            tag = tags.pop(0)
            while len(tags) > 0:
                tag = tags.pop(0)
                ts = self.parse_timestamp(tag)

                if ts is not None:
                    timestamp = ts
                else:
                    await ctx.send(
                        "`｡(*^▽^*)ゞ` no entendi... q es '" + str(
                            tag) + "' ?")
                    return

            (save_year, save_week, _, _) = self.get_date(timestamp)
            await self.get_all_plots(ctx, save_year, save_week)
            return

        if tags[0].lower() == "dump":
            tag = tags.pop(0)
            while len(tags) > 0:
                tag = tags.pop(0)
                ts = self.parse_timestamp(tag)

                if ts is not None:
                    timestamp = ts
                else:
                    target = self.get_target(ctx, tag, None)
                    if target is None:
                        await ctx.send(
                            "`｡(*^▽^*)ゞ` no entendi... q es '" + str(
                                tag) + "' ?")
                        return

            (save_year, save_week, _, _) = self.get_date(timestamp)
            await self.get_data(ctx, target, save_year, save_week)
            return

        if tags[0].lower() == "dump_all":
            if str(target) != "Grillo#6124":
                await ctx.send(
                    "`┬┴┬┴┤(･_├┬┴┬┴` no quiero")
                return
            tag = tags.pop(0)
            while len(tags) > 0:
                tag = tags.pop(0)
                ts = self.parse_timestamp(tag)

                if ts is not None:
                    timestamp = ts
                else:
                    await ctx.send(
                        "`｡(*^▽^*)ゞ` no entendi... q es '" + str(
                            tag) + "' ?")
                    return

            (save_year, save_week, _, _) = self.get_date(timestamp)
            await self.get_all_data(ctx, save_year, save_week)
            return

        if tags[0].lower() == "last_pattern" or tags[0].lower() == "lwp":
            tag = tags.pop(0)
            pattern = None
            while len(tags) > 0:
                tag = tags.pop(0)
                ts = self.parse_timestamp(tag)

                if tag.lower() in PATTERN_MSG:
                    pattern = tag
                elif ts is not None:
                    timestamp = ts
                else:
                    target = self.get_target(ctx, tag, None)
                    if target is None:
                        await ctx.send(
                            "`｡(*^▽^*)ゞ` no entendi... q es '" + str(
                                tag) + "' ?")
                        return

            (save_year, save_week, _, _) = self.get_date(timestamp)
            if pattern is None:
                await ctx.send("`｢(ﾟﾍﾟ)` q patron?")
                return

            await self.set_last_pattern(ctx, target, save_year, save_week, pattern)
            return

        # Es insersion de datos
        stalk_count = tags.pop()
        if not stalk_count.isdigit():
            await ctx.send("`~(>_<~)` no entiendo")
            return

        stalk_count = int(stalk_count)
        save_time = None
        while len(tags) > 0:
            tag = tags.pop(0)
            ts = self.parse_timestamp(tag)

            if tag.lower() in TIME_MSG:
                save_time = 0 if tag.lower() == "am" else 1
            elif tag.lower() in DATE_MSG:
                count = 1
                for day in DATE_MSG:
                    if tag.lower() == day:
                        save_day = count
                        break
                    count += 1
            elif ts is not None:
                timestamp = ts
            else:
                target = self.get_target(ctx, tag, None)
                if target is None:
                    return

        (
            save_year, 
            save_week, 
            save_day, 
            save_time_ts) = self.get_date(timestamp)
        save_time = save_time_ts if save_time is None else save_time
        save_time = save_time if save_day != 0 else 0

        await self.update_data(
            ctx, target, 
            save_year, save_week, save_day, save_time, 
            stalk_count)

