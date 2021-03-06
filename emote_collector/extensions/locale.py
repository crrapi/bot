#!/usr/bin/env python3
# encoding: utf-8

import typing

import discord
from discord.ext import commands

from .. import utils
from ..utils import i18n

GET_TRANSLATIONS = (
	'zeigen',  # de_DE
	'obtener',  # es_ES
	'mutat',  # hu_HU
)

SET_TRANSLATIONS = (
	'setzen',  # de_DE
	'establecer',  # es_ES
	'állít',  # hu_HU
)

class InvalidLocaleError(commands.BadArgument):
	def __init__(self):
		super().__init__(
			# Translator's note: if there's no good translation for "locale",
			# or it's not a common word in your language, feel free to use "language" instead for this file.
			_('Invalid locale. The valid locales are: {locales}').format(
				locales=', '.join(i18n.locales)))

def Locale(argument):
	if argument not in i18n.locales:
		raise InvalidLocaleError
	return argument

class Locales:
	def __init__(self, bot):
		self.bot = bot

	@commands.command(aliases=(
		'languages',  # en_US
		'sprachen',  # de_DE
		'idiomas',  # es_ES (languages)
		'lugares',  # es_ES (places)
		'nyelvek',  # hu_HU
	))
	async def locales(self, context):
		"""Lists the valid locales you can use."""
		await context.send(', '.join(sorted(i18n.locales)))

	@commands.group(name='locale', aliases=(
		'language',  # en_US
		'sprache',  # de_DE
		'idioma',  # es_ES (language)
		'lugar',  # es_ES (place)
		'nyelv',  # hu_HU
	))
	async def locale_command(self, context):
		"""Commands relating to modifying the locale.
		This command does nothing on its own; all functionality is in subcommands.
		"""
		pass

	@locale_command.command(name='get', aliases=GET_TRANSLATIONS)
	async def get_locale_command(self, context, channel: typing.Optional[discord.TextChannel] = None):
		"""Get the locale for a channel or yourself.

		If a channel is not provided, this command gets your current locale.
		"""

		if channel is None:
			user_locale = await self.locale(context.message)
			await context.send(_('Your current locale is: {user_locale}').format(**locals()))

		else:
			channel_or_guild_locale = await self.channel_or_guild_locale(channel) or i18n.default_locale
			await context.send(_(
				'The current locale for that channel is: {channel_or_guild_locale}').format(**locals()))

	@locale_command.command(name='set', aliases=SET_TRANSLATIONS)
	async def set_locale_command(self, context, channel: typing.Optional[discord.TextChannel], locale: Locale):
		"""Set the locale for a channel or yourself.

		Manage Messages is required to change the locale of a whole channel.
		If the channel is left blank, this command sets your user locale.
		"""

		if channel is None:
			await self.set_user_locale(context.author.id, locale)

		elif (
			not context.author.guild_permissions.manage_messages
			or not await self.bot.is_owner(context.author)
		):
			raise commands.MissingPermissions(('manage_messages',))

		else:
			await self.set_channel_locale(context.guild.id, channel.id, locale)

		await context.try_add_reaction(utils.SUCCESS_EMOJIS[True])

	@commands.group(name='serverlocale', aliases=(
		'serversprachen',  # de_DE
		'idioma-servidor',  # es_ES (server language)
		'idioma-del-servidor',  # es_ES (server language)
		'lugar-servidor',  # es_ES (server place)
		'lugar-del-servidor',  # es_ES (server place)
		'szervernyelv',  # hu_HU
	))
	@commands.guild_only()
	async def guild_locale_command(self, context):
		"""Commands relating to modifying the server locale.
		This command does nothing on its own; all functionality is in subcommands.
		"""
		pass

	@guild_locale_command.command(name='get', aliases=GET_TRANSLATIONS)
	async def get_guild_locale_command(self, context):
		guild_locale = await self.guild_locale(context.guild.id) or i18n.default_locale
		await context.send(_('The current locale for this server is: {guild_locale}').format(**locals()))

	@guild_locale_command.command(name='set', aliases=SET_TRANSLATIONS)
	@commands.has_permissions(manage_messages=True)
	async def set_guild_locale_command(self, context, locale: Locale):
		await self.set_guild_locale(context.guild.id, locale)
		await context.try_add_reaction(utils.SUCCESS_EMOJIS[True])

	async def locale(self, message):
		user = message.webhook_id or message.author.id

		if not message.guild:
			channel = None
			guild = None
		else:
			channel = message.channel.id
			guild = message.guild.id

		return await self.user_channel_or_guild_locale(user, channel, guild) or i18n.default_locale

	async def user_channel_or_guild_locale(self, user, channel, guild=None):
		return await self.bot.pool.fetchval("""
			SELECT COALESCE(
				(
					SELECT locale
					FROM   locales
					WHERE  "user" = $1),
				(
					SELECT locale
					FROM   locales
					WHERE  channel = $2),
				(
					SELECT locale
					FROM   locales
					WHERE      guild = $3
					       AND channel IS NULL
					       AND "user" IS NULL)
			)
		""", user, channel, guild)

	async def channel_or_guild_locale(self, channel):
		return await self.bot.pool.fetchval("""
			SELECT COALESCE(
				(
					SELECT locale
					FROM   locales
					WHERE  channel = $1),
				(
					SELECT locale
					FROM   locales
					WHERE      guild = $2
					       AND channel IS NULL
					       AND "user" IS NULL)
			)
		""", channel.id, channel.guild.id)

	async def guild_locale(self, guild):
		return await self.bot.pool.fetchval("""
			SELECT locale
			FROM   locales
			WHERE      guild = $1
			       AND channel IS NULL
			       AND "user" IS NULL
		""", guild)

	async def set_guild_locale(self, guild, locale):
		# connection/transaction probably isn't necessary for this, right?
		await self.bot.pool.execute("""
			DELETE FROM
			locales
			WHERE     guild = $1
			      AND channel IS NULL
			      AND "user"  IS NULL;
		""", guild)
		await self.bot.pool.execute("""
			INSERT INTO locales (guild, locale)
			VALUES ($1, $2);
		""", guild, locale)

	async def set_channel_locale(self, guild, channel, locale):
		await self.bot.pool.execute("""
			INSERT INTO locales (guild, channel, locale)
			VALUES ($1, $2, $3)
			ON CONFLICT (guild, channel) DO UPDATE
			SET locale = EXCLUDED.locale
		""", guild, channel, locale)

	async def set_user_locale(self, user, locale):
		await self.bot.pool.execute("""
			INSERT INTO locales ("user", locale)
			VALUES ($1, $2)
			ON CONFLICT ("user") DO UPDATE
			SET locale = EXCLUDED.locale
		""", user, locale)

	async def delete_user_account(self, user_id):
		await self.bot.pool.execute('DELETE FROM locales WHERE "user" = $1', user_id)

def setup(bot):
	bot.add_cog(Locales(bot))
