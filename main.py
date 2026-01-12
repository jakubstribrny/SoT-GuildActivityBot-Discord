import discord
from discord.ext import commands, tasks
import mysql.connector
from mysql.connector import Error as MySQLError
from apikeys import *
from datetime import datetime, timedelta
import time
import logging
import atexit
import asyncio
import sys

logging.basicConfig(filename='bot_log.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Create a handler for logging.infoing logs to the console
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)

# Create a formatter for the console logs
console_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

# Set the formatter for the console handler
console_handler.setFormatter(console_formatter)

# Add the console handler to the root logger
logging.getLogger().addHandler(console_handler)

intents = discord.Intents.default()
intents.members = True
intents.voice_states = True

client = commands.Bot(command_prefix="/", intents=discord.Intents.all())

sail_start_times = {}

# Set the connection timeout here (in seconds)
connection_timeout = 20

# Maximum number of retry attempts
MAX_RETRIES = 5

# Sleep time between retry attempts (in seconds)
RETRY_DELAY = 5

def connect_to_mysql():
    try:
        db_connection = mysql.connector.connect(
            host="185.32.183.90",
            user="unbroken",
            password="HorizonZeroDawn1@",
            database="test",
            connect_timeout=connection_timeout, # Set the connect_timeout parameter
            auth_plugin='mysql_native_password'
        )
        if db_connection.is_connected():
            return db_connection
    except MySQLError as e:
        logging.info("Error while connecting to MySQL:", e)
        return None

def execute_query_with_retry(connection, query, params=None):
    retry_count = 0
    while retry_count < MAX_RETRIES:
        try:
            cursor = connection.cursor()
            if params is not None:    
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            return cursor
        except MySQLError as e:
            logging.error("Error executing query:", e)
            if "Broken pipe" in str(e):  # Check if error is due to broken pipe
                logging.info("Attempting to reconnect...")
                connection.reconnect()  # Attempt to reconnect to the database
            retry_count += 1
            logging.info(f"Retrying in {RETRY_DELAY} seconds...")
            time.sleep(RETRY_DELAY)
    # If all retry attempts fail, return None
    logging.error("Failed to execute query after multiple attempts.")
    return None

def on_exit():
    try:
        logging.info('Vypínám bota...')
        logging.info('Bot byl vypnut.')
        # Add code here to log out from Discord or perform any cleanup tasks
        if client.is_closed():
            return
        loop = asyncio.get_event_loop()
        loop.run_until_complete(client.close())
    except Exception as e:
        logging.error(f"Chyba při ukončování bota: {e}")

# Register the on_exit function to be called when the script exits
atexit.register(on_exit)

@client.event
async def on_ready():
    logging.info("Bot je online")
    client.loop.create_task(check_active_users())
#########################################################################################################
##                                        PRIPOJENI NOVACKA                                            ##
#########################################################################################################
@client.event
async def on_member_join(member):
    channel = client.get_channel(1214360313114263582)
    pravidla = 1188611760245186612
    if channel is not None:
        mention = f"<@{member.id}>"
        mention_pravidla = f"<#{pravidla}>"
        await channel.send(f"Vítej mezi námi piráty, {mention}! Prosím, nezapomeň si přečíst naše zásady a jak to tu chodí v kanálu {mention_pravidla}.")

    role = discord.utils.get(member.guild.roles, name="Sailor")
    if role is not None:
        await member.add_roles(role)
        logging.info(f"Pridan '{role.name}' k {member.display_name}")
#########################################################################################################
##                                        KONEC NOVÁČKA                                                ##
#########################################################################################################
##                                        VYTVARENI CHANNELU                                           ##
#########################################################################################################
@client.event
async def on_voice_state_update(member, before, after):
    join_channel_name = "📞〢Create a crew"

    if after.channel and after.channel.name == join_channel_name:
        if not is_temp_channel_by_creator(member.id):
            username = member.display_name
            default_name = f"{username}'s channel"
            logging.info(f"{username} vytvořil svůj kanál.")
            temp_channel = await member.guild.create_voice_channel(default_name, category=after.channel.category)
            await member.move_to(temp_channel)
            add_temp_channel(temp_channel.id, default_name, member.id)  # Store default name in the database

            # Set permissions for the member
            await temp_channel.set_permissions(member, manage_channels=True)
        else:
            await member.send("Už máš vytvořený svůj dočasný kanál!")
            temp_channel_name = get_temp_channel_name(member.id)
            if temp_channel_name:
                temp_channel = discord.utils.get(member.guild.voice_channels, name=temp_channel_name)
                if temp_channel:
                    await member.move_to(temp_channel)
                else:
                    logging.error("Failed to find the temporary channel.")
            else:
                logging.error("Failed to retrieve the temporary channel name from the database.")

    elif before.channel and is_temp_channel(before.channel.id):
        creator_id = get_creator_id(before.channel.id)
        logging.info(f"{creator_id} se odpojil z kanálu {before.channel.id}")
        if not before.channel.members:
            update_temp_channel_name(creator_id, before.channel.name)
            await before.channel.delete()
            remove_temp_channel(creator_id)

################# FUNKCE #########################################################################################
def add_temp_channel(channel_id, channel_name, creator_id):
    try:
        db_connection = connect_to_mysql()
        if db_connection:
            cursor = execute_query_with_retry(db_connection, "SELECT channel_id FROM temp_channels WHERE creator_id = %s", (creator_id,))
            existing_channel_id = cursor.fetchone()

            if existing_channel_id:
                cursor = execute_query_with_retry(db_connection, "UPDATE temp_channels SET channel_id = %s WHERE creator_id = %s", (channel_id, creator_id))
            else:
                cursor = execute_query_with_retry(db_connection, "INSERT INTO temp_channels (channel_id, channel_name, creator_id) VALUES (%s, %s, %s)", (channel_id, channel_name, creator_id))

            db_connection.commit()
        else:
            logging.error("Failed to connect to MySQL.")
    except Exception as e:
        logging.error(f"Error occurred while adding or updating temp channel: {e}")
    finally:
        if db_connection and db_connection.is_connected():
            cursor.close()
            db_connection.close()

def get_temp_channel_name(creator_id):
    try:
        db_connection = connect_to_mysql()
        if db_connection:
            cursor = execute_query_with_retry(db_connection, "SELECT channel_name FROM temp_channels WHERE creator_id = %s", (creator_id,))
            result = cursor.fetchone()

            if result:
                return result[0] 
            else:
                return None     
        else:
            logging.error("Failed to connect to MySQL.")
    except Exception as e:
        logging.error(f"Error occurred while getting name of temp channel: {e}")
    finally:
        if db_connection and db_connection.is_connected():
            cursor.close()
            db_connection.close()

def is_temp_channel(channel_id):                                        
    try:
        db_connection = connect_to_mysql()
        if db_connection:
            cursor = execute_query_with_retry(db_connection, "SELECT * FROM temp_channels WHERE channel_id = %s", (channel_id,))
            return cursor.fetchone() is not None
        else:
            logging.error("Failed to connect to MySQL.")
            return False
    except Exception as e:
        logging.error(f"Error occurred while checking if channel is temporary: {e}")
        return False
    finally:
        if db_connection and db_connection.is_connected():
            cursor.close()
            db_connection.close()


def get_creator_id(channel_id):
    try:
        db_connection = connect_to_mysql()
        if db_connection:
            cursor = execute_query_with_retry(db_connection, "SELECT creator_id FROM temp_channels WHERE channel_id = %s", (channel_id,))
            result = cursor.fetchone()
            return result[0] if result else None
        else:
            logging.error("Failed to connect to MySQL.")
            return None
    except Exception as e:
        logging.error(f"Error occurred while getting creator ID: {e}")
        return None
    finally:
        if db_connection and db_connection.is_connected():
            db_connection.close()
    
def is_temp_channel_by_creator(creator_id):
    try:
        db_connection = connect_to_mysql()
        if db_connection:
            cursor = execute_query_with_retry(db_connection, "SELECT channel_id FROM temp_channels WHERE creator_id = %s", (creator_id,))
            result = cursor.fetchone()
            return result is not None and result[0] > -1
        else:
            logging.error("Failed to connect to the database.")
            return None
    except Exception as e:
        logging.error(f"An error occurred while checking if channel is by creator: {e}")
        return None
    finally:
        if db_connection and db_connection.is_connected():
            db_connection.close()

def update_temp_channel_name(creator_id, channel_name):
    try:
        db_connection = connect_to_mysql()
        if db_connection:
            cursor = execute_query_with_retry(db_connection, "SELECT channel_id FROM temp_channels WHERE creator_id = %s", (creator_id,))
            existing_channel_id = cursor.fetchone()
            if existing_channel_id:
                cursor = execute_query_with_retry(db_connection, "UPDATE temp_channels SET channel_name = %s WHERE creator_id = %s", (channel_name, creator_id))
                db_connection.commit()
            else:
                db_connection.commit()
    except Exception as e:
        logging.error(f"Error occured while getting updating temp channel name: {e}")
        return None
    finally:
        if db_connection and db_connection.is_connected():
            cursor.close()
            db_connection.close()

def remove_temp_channel(creator_id):                                    ############### VYMAZÁVÁ CAHNNEL
    try:
        db_connection = connect_to_mysql()
        if db_connection:
            cursor = execute_query_with_retry(db_connection, "UPDATE temp_channels SET channel_id = -1 WHERE creator_id = %s", (creator_id,))
            db_connection.commit()
    except Exception as e:
        logging.error(f"Error occured while setting channel id to -1: {e}")
        return None
    finally:
        if db_connection and db_connection.is_connected():
            cursor.close()
            db_connection.close()
#########################################################################################################
##                                        KONEC CHANNELŮ                                               ##
#########################################################################################################
##                                        SETSAIL AKTIVITA                                             ##
#########################################################################################################
@client.command()
async def sail(ctx):
    allowed_role_ids = [1214350282595504249]
    user_role_ids = [role.id for role in ctx.author.roles]
    
    if any(role_id in allowed_role_ids for role_id in user_role_ids):
        await ctx.message.delete()
        embed = discord.Embed(
            title="Aktivita na moři",
            description="Okno pro aktivitu na moři slouží k tomu, aby si uživatel mohl pohodlně zapisovat aktivitu v guildě. Níže naleznete jak na to.",
            color=0x2ded60
        )
        embed.set_image(url='https://cdn.discordapp.com/attachments/917518710099542026/1230598587537162311/wallpapersden.com_halo-spartan-sea-of-thieves_7680x4320.jpg?ex=6633e73e&is=6621723e&hm=9efe9aedc5e585ddd93a628b0c332faba6f096575c487aa70b15c50a9ad38ff2&')
        embed.add_field(name="Zahájení plavby", value="Klikni na start ▶️ pro zahájení plavby", inline=True)
        embed.add_field(name="Ukončení plavby", value="Klikni na stop ⏹️ pro ukončení plavby", inline=True)
        msg = await ctx.send(embed=embed)
        await msg.add_reaction("▶️") 
        await msg.add_reaction("⏹️")  
    else:
        await ctx.send("Nemáš dostatečné práva na to založit aktivitní plugin!")

@client.event
async def on_reaction_add(reaction, user):
    aktivita_channel = client.get_channel(1195369280427012276)
    logging.info(f"Reaction: {reaction.emoji}, User: {user.name}, ID: {user.id}")

    if user == client.user:
        return

    if str(reaction.emoji) == "▶️":  
        if user.id in sail_start_times:
            await user.send(f"{user.mention} již jsi zahájil plavbu!")
            await reaction.remove(user)
        else:
            sail_start_times[user.id] = datetime.now()
            logging.info(f"Start time recorded for {user.name}")
            zacatek_plavby = discord.Embed(
                title="Zahájení plavby",
                description=f"{user.mention} započal svou plavbu!",
                color=0x672ded
            )
            zacatek_plavby.set_author(name=user.display_name, icon_url=user.avatar)
            await aktivita_channel.send(embed=zacatek_plavby)
            await reaction.remove(user)

    elif str(reaction.emoji) == "⏹️":
        if user.id in sail_start_times:
            start_time = sail_start_times.pop(user.id)
            end_time = datetime.now()
            duration = end_time - start_time
            duration_str = str(duration).split(".")[0]
            logging.info(f"End time recorded for {user.name}")
            konec_plavby = discord.Embed(
                title="Ukončení plavby",
                description=f"{user.mention} byl na moři {duration_str}!",
                color=0x672ded
            )
            konec_plavby.set_author(name=user.display_name, icon_url=user.avatar)
            await aktivita_channel.send(embed=konec_plavby)
            await reaction.remove(user)

            store_sail_time(user.id, duration)

        else:
            await user.send(f"{user.mention} ještě si nezačal plavbu!")
            await reaction.remove(user)

def store_sail_time(user_id, duration):
    total_seconds = int(duration.total_seconds())
    try:
        db_connection = connect_to_mysql()
        if db_connection:
            cursor = execute_query_with_retry(db_connection, "SELECT recent, 2weeks, total FROM sail_times WHERE user = %s", (user_id,))
            result = cursor.fetchone()
            if result:
                cursor = execute_query_with_retry(db_connection, "UPDATE sail_times SET recent = %s, 2weeks = 2weeks + %s, total = total + %s WHERE user = %s", (total_seconds, total_seconds, total_seconds, user_id))
                db_connection.commit()
            else:
                cursor = execute_query_with_retry(db_connection, "INSERT INTO sail_times (user, recent, 2weeks, total) VALUES (%s, %s, %s, %s)", (user_id, total_seconds, total_seconds, total_seconds))
                db_connection.commit()
    except Exception as e:
        logging.error(f"Error occured while storing sail time: {e}")
        return None
    finally:
        if db_connection and db_connection.is_connected():
            cursor.close()
            db_connection.close()


@client.command()
async def end_all_sails(ctx):
    aktivita_channel = client.get_channel(1195369280427012276)
    for user_id, start_time in sail_start_times.items():
        user = await client.fetch_user(user_id)
        if user:
            end_time = datetime.now()
            duration = end_time - start_time
            duration_str = str(duration).split(".")[0]
            logging.info(f"End time recorded for {user.name}")
            konec_plavby = discord.Embed(
                title="Ukončení plavby",
                description=f"{user.mention} byl na moři {duration_str}!",
                color=0x672ded
            )
            konec_plavby.set_author(name=user.display_name, icon_url=user.avatar)
            await aktivita_channel.send(embed=konec_plavby)

            # Store sail time
            store_sail_time(user_id, duration)

    # Clear all sail start times
    sail_start_times.clear()
#########################################################################################################
##                                      KONEC SETSAIL                                                  ##
#########################################################################################################
##                                      NAVOD NA AKTIVITU                                              ##
#########################################################################################################
@client.command()
async def navod_na_aktivitu(ctx):
            allowed_role_ids = [1214350282595504249]
            user_role_ids = [role.id for role in ctx.author.roles]
            pravidla = 1215035529528213617
            if any(role_id in allowed_role_ids for role_id in user_role_ids):
                mention_pravidla = f"<#{pravidla}>"
                await ctx.message.delete()
                navod = discord.Embed(
                    title="Návod na aktivitu v guildě",
                    description=f"Pro přiblížení, jak to u nás funguje, jsme si pro vás připravili návod.\nAktivita v naší guildě je důležitým aspektem a rádi bychom, abyste ji dodržovali.\nAktivní členi mohou dostat odměnu ze soutěží.\n_____________________\n**1.** Při zahájení plavby pro guildu jděte do kanálu {mention_pravidla}.\n**2.** Pro zapnutí počítání nahraného času odklikněte reakci ▶️(start).\n**3.** Po 2. kroku vám **bot začne počítat čas** a vy můžete jít do hry.\n**4.**Po dohrání běžte opět do {mention_pravidla} a klikněte na reakci ⏹️(stop).\nVaše aktivita tímto byla úspěšně zaznamenána a váš čas uložen do databáze.\nUkládá se jak čas poslední, tak i čas dohromady.\nProsíme vás, opětujte tento postup, při každé nové plavbě.\nUnbroken Warriors",
                    color=0xc4352b
                )
                navod.set_image(url='https://cdn.discordapp.com/attachments/885247213209534514/1215113368310910976/Screenshot_2023-12-22_at_9.25.45.png?ex=65fb9182&is=65e91c82&hm=0823739219ab8a743d42ef40df5097d16c68c285fb6d1327b8f133bd22047799&')
                await ctx.send(embed=navod)

#########################################################################################################
##                                      KONEC NAVODU                                                   ##
#########################################################################################################
##                                      VYPSANI TABULKY                                                ##
#########################################################################################################
@client.command()
async def vypsat_tabulku(ctx):
    allowed_role_ids = [1214350282595504249, 1188606447211257926]
    user_role_ids = [role.id for role in ctx.author.roles]
    guildmate = 1188608335486914730
    mention_everyone = f"<@&{guildmate}>"

    try:
        db_connection = connect_to_mysql()
        if db_connection:

            cursor = execute_query_with_retry(db_connection, "SELECT user, 2weeks FROM sail_times ORDER BY 2weeks DESC")
            rows = cursor.fetchall()

            if any(role_id in allowed_role_ids for role_id in user_role_ids):
                await ctx.message.delete()
                await ctx.send("https://cdn.discordapp.com/attachments/1214300389739077663/1215331349272207430/Infoline.png?ex=65fc5c85&is=65e9e785&hm=ead9c4f3f3dfac3e5df15adf779e9eef7658442e11f403affe9187243e4f598d&")
                await ctx.send(f"**Tabulka aktivity!, příští za 2 týdny. {mention_everyone}**")
                header = "+---------------------+--------------+\n"
                header += "|       Nickname      | Počet hodin  |\n"
                header += "+---------------------+--------------+\n"
                table = header

                for idx, row in enumerate(rows, start=1):
                    user_id = row[0]
                    weeks_hours = row[1]
                    hours = weeks_hours // 3600
                    minutes = (weeks_hours % 3600) // 60
                    guild = await client.fetch_guild(1188553687564554240)
                    cas = f"{hours}h. {minutes}min."
                    try:
                        member = await guild.fetch_member(user_id)
                        nickname = member.nick
                    except discord.NotFound:
                        nickname = f"Neznámý uživatel (ID: {user_id})"
                    
                    if nickname is None:
                        user = await client.fetch_user(user_id)
                        nickname = user.name
                    
                    if idx == 1:
                        position_emoji = "🥇"
                        top_member = member
                    elif idx == 2:
                        position_emoji = "🥈"
                    elif idx == 3:
                        position_emoji = "🥉"
                    else:
                        position_emoji = "📌"
                    
                    table += f"| {position_emoji}{nickname:15} |  {cas:12} |\n"

                    role = discord.utils.get(ctx.guild.roles, id=1215840369724620850)
                                # Check if the member has the top role
                    if idx == 1:
                        if role not in member.roles:
                            await top_member.add_roles(role)
                    else:
                        if role in member.roles:
                            if member == top_member:
                                continue
                            else:
                                await member.remove_roles(role)
                        else:
                            continue

                table += "+---------------------+--------------+"
                await ctx.send("```" + table + "```")

                cursor.execute("UPDATE sail_times SET 2weeks = 0")
                db_connection.commit()
                await ctx.send("https://cdn.discordapp.com/attachments/1214300389739077663/1215331349272207430/Infoline.png?ex=65fc5c85&is=65e9e785&hm=ead9c4f3f3dfac3e5df15adf779e9eef7658442e11f403affe9187243e4f598d&")
            else:
                await ctx.send("Nemáš oprávnění k použití tohoto příkazu.")
    except Exception as e:
        logging.error(f"Error occurred while printing table: {e}")
    finally:
        if cursor:
            cursor.close()
        if db_connection and db_connection.is_connected():
            db_connection.close()
#########################################################################################################
##                                      KONEC TABULKY                                                  ##
#########################################################################################################
##                                        LEVELS                                                       ##
#########################################################################################################
async def levels(ctx):
    role_0 = discord.utils.get(ctx.guild.roles, name="Úroveň 0")
    role_1 = discord.utils.get(ctx.guild.roles, name="Úroveň 1")
    role_2 = discord.utils.get(ctx.guild.roles, name="Úroveň 2")
    role_3 = discord.utils.get(ctx.guild.roles, name="Úroveň 3")
    role_4 = discord.utils.get(ctx.guild.roles, name="Úroveň 4")
    role_5 = discord.utils.get(ctx.guild.roles, name="Úroveň 5")
    role_6 = discord.utils.get(ctx.guild.roles, name="Úroveň 6")
    role_7 = discord.utils.get(ctx.guild.roles, name="Úroveň 7")
    role_8 = discord.utils.get(ctx.guild.roles, name="Úroveň 8")
    role_9 = discord.utils.get(ctx.guild.roles, name="Úroveň 9")

    channel = client.get_channel(1215809848202104873)
    try:
        db_connection = connect_to_mysql()
        if db_connection:

            cursor = execute_query_with_retry(db_connection, "SELECT user, SUM(total) FROM sail_times GROUP BY user")
            radky = cursor.fetchall()

            for row in radky:
                user_id, total_seconds = row
                try:
                    member = await ctx.guild.fetch_member(user_id)
                except discord.NotFound:
                        member = f"Neznámý uživatel (ID: {user_id})"
                if isinstance(member, discord.Member):
                    if total_seconds >= 250000 and role_0 in member.roles:
                        await member.remove_roles(role_0)
                        await member.add_roles(role_1)
                        await channel.send("https://cdn.discordapp.com/attachments/1214300389739077663/1215331349272207430/Infoline.png?ex=65fc5c85&is=65e9e785&hm=ead9c4f3f3dfac3e5df15adf779e9eef7658442e11f403affe9187243e4f598d&")
                        await channel.send(f"{member.display_name} postoupil na Úroveň 1!")
                        await channel.send("https://cdn.discordapp.com/attachments/1214300389739077663/1215331349272207430/Infoline.png?ex=65fc5c85&is=65e9e785&hm=ead9c4f3f3dfac3e5df15adf779e9eef7658442e11f403affe9187243e4f598d&")
                    elif total_seconds >= 500000 and role_1 in member.roles:
                        await member.remove_roles(role_1)
                        await member.add_roles(role_2)
                        await channel.send("https://cdn.discordapp.com/attachments/1214300389739077663/1215331349272207430/Infoline.png?ex=65fc5c85&is=65e9e785&hm=ead9c4f3f3dfac3e5df15adf779e9eef7658442e11f403affe9187243e4f598d&")
                        await channel.send(f"{member.display_name} postoupil na Úroveň 2!")
                        await channel.send("https://cdn.discordapp.com/attachments/1214300389739077663/1215331349272207430/Infoline.png?ex=65fc5c85&is=65e9e785&hm=ead9c4f3f3dfac3e5df15adf779e9eef7658442e11f403affe9187243e4f598d&")
                    elif total_seconds >= 500000 and role_1 in member.roles:
                        await member.remove_roles(role_1)
                        await member.add_roles(role_2)
                        await channel.send("https://cdn.discordapp.com/attachments/1214300389739077663/1215331349272207430/Infoline.png?ex=65fc5c85&is=65e9e785&hm=ead9c4f3f3dfac3e5df15adf779e9eef7658442e11f403affe9187243e4f598d&")
                        await channel.send(f"{member.display_name} postoupil na Úroveň 2!")
                        await channel.send("https://cdn.discordapp.com/attachments/1214300389739077663/1215331349272207430/Infoline.png?ex=65fc5c85&is=65e9e785&hm=ead9c4f3f3dfac3e5df15adf779e9eef7658442e11f403affe9187243e4f598d&")

                    elif total_seconds >= 750000 and role_2 in member.roles:
                        await member.remove_roles(role_2)
                        await member.add_roles(role_3)
                        await channel.send("https://cdn.discordapp.com/attachments/1214300389739077663/1215331349272207430/Infoline.png?ex=65fc5c85&is=65e9e785&hm=ead9c4f3f3dfac3e5df15adf779e9eef7658442e11f403affe9187243e4f598d&")
                        await channel.send(f"{member.display_name} postoupil na Úroveň 3!")
                        await channel.send("https://cdn.discordapp.com/attachments/1214300389739077663/1215331349272207430/Infoline.png?ex=65fc5c85&is=65e9e785&hm=ead9c4f3f3dfac3e5df15adf779e9eef7658442e11f403affe9187243e4f598d&")

                    elif total_seconds >= 1000000 and role_3 in member.roles:
                        await member.remove_roles(role_3)
                        await member.add_roles(role_4)
                        await channel.send("https://cdn.discordapp.com/attachments/1214300389739077663/1215331349272207430/Infoline.png?ex=65fc5c85&is=65e9e785&hm=ead9c4f3f3dfac3e5df15adf779e9eef7658442e11f403affe9187243e4f598d&")
                        await channel.send(f"{member.display_name} postoupil na Úroveň 4!")
                        await channel.send("https://cdn.discordapp.com/attachments/1214300389739077663/1215331349272207430/Infoline.png?ex=65fc5c85&is=65e9e785&hm=ead9c4f3f3dfac3e5df15adf779e9eef7658442e11f403affe9187243e4f598d&")

                    elif total_seconds >= 1250000 and role_4 in member.roles:
                        await member.remove_roles(role_4)
                        await member.add_roles(role_5)
                        await channel.send("https://cdn.discordapp.com/attachments/1214300389739077663/1215331349272207430/Infoline.png?ex=65fc5c85&is=65e9e785&hm=ead9c4f3f3dfac3e5df15adf779e9eef7658442e11f403affe9187243e4f598d&")
                        await channel.send(f"{member.display_name} postoupil na Úroveň 5!")
                        await channel.send("https://cdn.discordapp.com/attachments/1214300389739077663/1215331349272207430/Infoline.png?ex=65fc5c85&is=65e9e785&hm=ead9c4f3f3dfac3e5df15adf779e9eef7658442e11f403affe9187243e4f598d&")

                    elif total_seconds >= 1500000 and role_5 in member.roles:
                        await member.remove_roles(role_5)
                        await member.add_roles(role_6)
                        await channel.send("https://cdn.discordapp.com/attachments/1214300389739077663/1215331349272207430/Infoline.png?ex=65fc5c85&is=65e9e785&hm=ead9c4f3f3dfac3e5df15adf779e9eef7658442e11f403affe9187243e4f598d&")
                        await channel.send(f"{member.display_name} postoupil na Úroveň 6!")
                        await channel.send("https://cdn.discordapp.com/attachments/1214300389739077663/1215331349272207430/Infoline.png?ex=65fc5c85&is=65e9e785&hm=ead9c4f3f3dfac3e5df15adf779e9eef7658442e11f403affe9187243e4f598d&")

                    elif total_seconds >= 1750000 and role_6 in member.roles:
                        await member.remove_roles(role_6)
                        await member.add_roles(role_7)
                        await channel.send("https://cdn.discordapp.com/attachments/1214300389739077663/1215331349272207430/Infoline.png?ex=65fc5c85&is=65e9e785&hm=ead9c4f3f3dfac3e5df15adf779e9eef7658442e11f403affe9187243e4f598d&")
                        await channel.send(f"{member.display_name} postoupil na Úroveň 7!")
                        await channel.send("https://cdn.discordapp.com/attachments/1214300389739077663/1215331349272207430/Infoline.png?ex=65fc5c85&is=65e9e785&hm=ead9c4f3f3dfac3e5df15adf779e9eef7658442e11f403affe9187243e4f598d&")

                    elif total_seconds >= 2000000 and role_7 in member.roles:
                        await member.remove_roles(role_7)
                        await member.add_roles(role_8)
                        await channel.send("https://cdn.discordapp.com/attachments/1214300389739077663/1215331349272207430/Infoline.png?ex=65fc5c85&is=65e9e785&hm=ead9c4f3f3dfac3e5df15adf779e9eef7658442e11f403affe9187243e4f598d&")
                        await channel.send(f"{member.display_name} postoupil na Úroveň 8!")
                        await channel.send("https://cdn.discordapp.com/attachments/1214300389739077663/1215331349272207430/Infoline.png?ex=65fc5c85&is=65e9e785&hm=ead9c4f3f3dfac3e5df15adf779e9eef7658442e11f403affe9187243e4f598d&")

                    elif total_seconds >= 2250000 and role_8 in member.roles:
                        await member.remove_roles(role_8)
                        await member.add_roles(role_9)
                        await channel.send("https://cdn.discordapp.com/attachments/1214300389739077663/1215331349272207430/Infoline.png?ex=65fc5c85&is=65e9e785&hm=ead9c4f3f3dfac3e5df15adf779e9eef7658442e11f403affe9187243e4f598d&")
                        await channel.send(f"{member.display_name} postoupil na Úroveň 9!")
                        await channel.send("https://cdn.discordapp.com/attachments/1214300389739077663/1215331349272207430/Infoline.png?ex=65fc5c85&is=65e9e785&hm=ead9c4f3f3dfac3e5df15adf779e9eef7658442e11f403affe9187243e4f598d&")
                    else:
                        continue
                else:
                    logging.warning(f"Could not fetch member or member is unknown: {member}")
    except Exception as e:
        logging.error(f"Error while getting level ups: {e}")
    finally:
        # Close the cursor and the database connection
        if cursor:
            cursor.close()
        if db_connection and db_connection.is_connected():
            db_connection.close()
#########################################################################################################       
##                                      PRIKAZ /STATS                                                  ##
#########################################################################################################
@client.command()
async def stats(ctx):
    allowed_channel_id = 1215809848202104873
    allowed_role_ids = [1188608335486914730]
    mention_channel = f"<#{allowed_channel_id}>"
    user_role_ids = [role.id for role in ctx.author.roles]
    if ctx.channel.id == allowed_channel_id:
        if any(role_id in allowed_role_ids for role_id in user_role_ids):
            db_connection = None
            cursor = None
            try:
                db_connection = connect_to_mysql()
                if db_connection:
                    cursor = execute_query_with_retry(db_connection, "SELECT recent, total FROM sail_times WHERE user = %s", (ctx.author.id,))
                    if cursor:
                        rows = cursor.fetchall()
                        if rows:
                            recent, total = rows[0]
                            # Further processing
                        else:
                            logging.info(f"No data found for this user.")
                        hours_recent = recent // 3600
                        minutes_recent = (recent % 3600) // 60
                        hours_total = total // 3600
                        minutes_total = (total % 3600) // 60
                        level_roles = ["Úroveň 0", "Úroveň 1", "Úroveň 2", "Úroveň 3", "Úroveň 4", "Úroveň 5", "Úroveň 6", "Úroveň 7", "Úroveň 8", "Úroveň 9"]

                        if hours_recent >= 5 or hours_recent == 0:
                            recent_cas = f"{hours_recent} hodin "
                        elif hours_recent < 5 and hours_recent != 1:
                            recent_cas = f"{hours_recent} hodiny "
                        elif hours_recent == 1:
                            recent_cas = f"{hours_recent} hodinu "

                        if minutes_recent >= 5 or minutes_recent == 0:
                            recent_cas += f"{minutes_recent} minut"
                        elif minutes_recent < 5 and minutes_recent != 1:
                            recent_cas += f"{minutes_recent} minuty"
                        elif minutes_recent == 1:
                            recent_cas += f"{minutes_recent} minutu"
                        ######################################################
                        if hours_total >= 5 or hours_total == 0:
                            total_cas = f"{hours_total} hodin "
                        elif hours_total < 5 and hours_total != 1:
                            total_cas = f"{hours_total} hodiny "
                        elif hours_total == 1:
                            total_cas = f"{hours_total} hodina "

                        if minutes_total >= 5 or minutes_total == 0:
                            total_cas += f"{minutes_total} minut"
                        elif minutes_total < 5 and minutes_total != 1:
                            total_cas += f"{minutes_total} minuty"
                        elif minutes_total == 1:
                            total_cas += f"{minutes_total} minuta"
                        
                        join_date = ctx.author.joined_at.strftime("%d.%m.%Y")
                        member_roles = ctx.author.roles
                        
                        member_level_role = None

                        await levels(ctx)


                        for role in member_roles:
                            if role.name in level_roles:
                                member_level_role = role.name
                                break

                        if member_level_role == "Úroveň 0":
                            remaining = 250000 - total
                            remaining_hours = remaining // 3600
                            remaining_minutes = (remaining % 3600) // 60
                            remaining_print =f"{remaining_hours}h {remaining_minutes}min hraní"
                        elif member_level_role == "Úroveň 1":
                            remaining = 500000 - total
                            remaining_hours = remaining // 3600
                            remaining_minutes = (remaining % 3600) // 60
                            remaining_print =f"{remaining_hours}h {remaining_minutes}min hraní"
                        elif member_level_role == "Úroveň 2":
                            remaining = 750000 - total
                            remaining_hours = remaining // 3600
                            remaining_minutes = (remaining % 3600) // 60
                            remaining_print = f"{remaining_hours}h {remaining_minutes}min hraní"
                        elif member_level_role == "Úroveň 3":
                            remaining = 1000000 - total
                            remaining_hours = remaining // 3600
                            remaining_minutes = (remaining % 3600) // 60
                            remaining_print = f"{remaining_hours}h {remaining_minutes}min hraní"
                        elif member_level_role == "Úroveň 4":
                            remaining = 1250000 - total
                            remaining_hours = remaining // 3600
                            remaining_minutes = (remaining % 3600) // 60
                            remaining_print = f"{remaining_hours}h {remaining_minutes}min hraní"
                        elif member_level_role == "Úroveň 5":
                            remaining = 1500000 - total
                            remaining_hours = remaining // 3600
                            remaining_minutes = (remaining % 3600) // 60
                            remaining_print = f"{remaining_hours}h {remaining_minutes}min hraní"
                        elif member_level_role == "Úroveň 6":
                            remaining = 1750000 - total
                            remaining_hours = remaining // 3600
                            remaining_minutes = (remaining % 3600) // 60
                            remaining_print = f"{remaining_hours}h {remaining_minutes}min hraní"
                        elif member_level_role == "Úroveň 7":
                            remaining = 2000000 - total
                            remaining_hours = remaining // 3600
                            remaining_minutes = (remaining % 3600) // 60
                            remaining_print = f"{remaining_hours}h {remaining_minutes}min hraní"
                        elif member_level_role == "Úroveň 8":
                            remaining = 2250000 - total
                            remaining_hours = remaining // 3600
                            remaining_minutes = (remaining % 3600) // 60
                            remaining_print = f"{remaining_hours}h {remaining_minutes}min hraní"
                        elif member_level_role == "Úroveň 9":
                            remaining_print = f"**Beast of activity**"

                        stats = discord.Embed(
                            title="STATISTIKY",
                            description=f"Poslední plavba trvala: {recent_cas}\nCelkově nahraný čas: {total_cas}\nGuildmate level: {member_level_role}\nLevel up za: {remaining_print}\nČlenem guildovního discordu od: {join_date}\n",
                            color=0xDA924B
                        )
                        avatar_url = ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url
                        stats.set_author(name=ctx.author.name, icon_url=avatar_url)
                        await ctx.send(embed=stats)
            except Exception as e:
                logging.error(f"Error occurred printing stats: {e}")
            finally:
                if cursor:
                    cursor.close()
                if db_connection and db_connection.is_connected():
                    db_connection.close()
        else:
            await ctx.send(f"Nemáš roli Guildmate, proto nemůžeš použít statistiky.")
    else:
        await ctx.send(f"Tento příkaz může být použit pouze v kanálu {mention_channel}.")

#########################################################################################################
##                                       KONEC STATS                                                   ##
#########################################################################################################
##                                        ODPOJENI Z SERVERU                                           ##
#########################################################################################################
@client.event
async def on_member_remove(member):
    channel = client.get_channel(1215771985771102268)
    if channel is not None:
        await channel.send(f"{member} nás opustil. :/")
        logging.info(f"User {member} left the discord.")
        # Remove the member's row from the sail_times table
    try:
        db_connection = connect_to_mysql()
        if db_connection:
            query = "DELETE FROM sail_times WHERE user = %s"
            cursor = db_connection.cursor()
            cursor.execute(query, (member.id,))
            db_connection.commit()
            logging.info(f"Removed sail_times record for user {member.id}.")
    except MySQLError as e:
        logging.error(f"Error while removing sail_times record for user {member.id}: {e}")
    finally:
        if cursor:
            cursor.close()
        if db_connection and db_connection.is_connected():
            db_connection.close()


@client.command()
async def remove_left_users(ctx):
    try:
        db_connection = connect_to_mysql()
        if db_connection:
            cursor = execute_query_with_retry(db_connection, "SELECT user FROM sail_times")
            radky = cursor.fetchall()
            for row in radky:
                user_id = row[0]  # Extract the user ID from the tuple
                try:
                    member = await ctx.guild.fetch_member(user_id)
                except discord.NotFound:
                    member = None  # User not found in the guild
                if not member:  # If the member is not found, it's not an instance of discord.Member
                    query = "DELETE FROM sail_times WHERE user = %s"
                    cursor.execute(query, (user_id,))  # Use user_id instead of member.id
                    db_connection.commit()
                    logging.info(f"Removed sail_times record for user {user_id}.")
    except MySQLError as e:
        logging.error(f"Error while removing sail_times record: {e}")
    finally:
        if cursor:
            cursor.close()
        if db_connection and db_connection.is_connected():
            db_connection.close()



@client.command()
async def export_user_ids(ctx):
    try:
        db_connection = connect_to_mysql()
        if db_connection:
            cursor = execute_query_with_retry(db_connection, "SELECT user FROM sail_times")
            rows = cursor.fetchall()
            
            user_data = []
            for row in rows:
                user_id = row[0]  # Extract the user ID from the tuple
                try:
                    member = await ctx.guild.fetch_member(user_id)
                    user_data.append(f'"{member.display_name}" = "{member.id}"')
                except discord.NotFound:
                    user_data.append(f'"Unknown User (ID: {user_id})" = "{user_id}"')
            
            # Write to a text file
            with open("user_ids.txt", "w") as file:
                for entry in user_data:
                    file.write(entry + "\n")
            
            await ctx.send("User IDs have been exported to user_ids.txt")
            logging.info("User IDs have been exported to user_ids.txt")
    except MySQLError as e:
        logging.error(f"Error while exporting user IDs: {e}")
    finally:
        if cursor:
            cursor.close()
        if db_connection and db_connection.is_connected():
            db_connection.close()

#########################################################################################################
##                                       KONEC ODPOJENI                                                ##
#########################################################################################################

users_with_messages_sent = {}
        
# Function to check and send messages for active users
async def check_active_users():
    sus_channel = client.get_channel(1217230711413669988)
    while True:
        for user_id, start_time in sail_start_times.items():
            user = await client.fetch_user(user_id)
            if user:
                duration = datetime.now() - start_time
                hours = duration.total_seconds() / 3600

                if 10 <= hours < 20:
                    if user_id not in users_with_messages_sent.get('greaterthan10', []):
                        info = discord.Embed(
                            title="SUS PLAVBA",
                            description=f"{user.mention} je na moři déle než 10 hodin!",
                            color=0x08A4CE
                        )
                        info.set_author(name=user.display_name, icon_url=user.avatar)
                        await sus_channel.send(embed=info)
                        await user.send("Už jsi na moři déle než 10 hodin!")
                        users_with_messages_sent.setdefault('greaterthan10', []).append(user_id)

                elif hours >= 20:
                    if user_id not in users_with_messages_sent.get('greaterthan20', []):
                        info = discord.Embed(
                            title="SUS PLAVBA",
                            description=f"{user.mention} je na moři déle než 20 hodin! Buď je to tryhard, zapomněl to vypnout nebo podvadí!",
                            color=0x08A4CE
                        )
                        info.set_author(name=user.display_name, icon_url=user.avatar)
                        await sus_channel.send(embed=info)
                        await user.send("Už jsi na moři déle než 20 hodin!")
                        users_with_messages_sent.setdefault('greaterthan20', []).append(user_id)

        await asyncio.sleep(180)

client.run(BOTTOKEN)