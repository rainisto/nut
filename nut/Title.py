#!/usr/bin/python3
# -*- coding: utf-8 -*-
import os
import re
import json
from nut import Titles
from nut import Print

from bs4 import BeautifulSoup
import requests
import time
import datetime
import calendar
import threading
import traceback
import sys
from nut import Nsps
import urllib.request
from nut import Config
try:
	import cdn
except BaseException:
	pass

try:
	from PIL import Image
except BaseException:
	import Image

fileLUT = {}
grabUrlInit = False
urlCache = {}
urlLock = threading.Lock()

if os.path.isfile('titledb/redirectCache.json'):
	with open('titledb/redirectCache.json', encoding="utf-8-sig") as f:
		urlCache = json.loads(f.read())

def grabCachedRedirectUrl(url, cookies=None):
	global grabUrlInit
	global urlCache
	global urlLock

	try:
		if url in urlCache:
			if not urlCache[url]:
				return None
			result = requests.get(urlCache[url], cookies=cookies)
			#result.url = urlCache[url]
			return result

		urlLock.acquire()
		# we need to slow this down so we dont get banned
		#Print.info('hitting ' + url)
		# time.sleep(0.1)
		result = requests.get(url, cookies=cookies)
		if result.status_code == 404:
			urlCache[url] = None
		elif result.status_code == 200:
			urlCache[url] = result.url
		else:
			# not sure but dont cache it
			return result

		with open('titledb/redirectCache.json', 'w') as outfile:
			json.dump(urlCache, outfile)
		urlLock.release()
		return result
	except BaseException:
		urlLock.release()
		raise

def getBaseId(id):
	if not id:
		return None
	titleIdNum = int(id, 16)
	return '{:02X}'.format(titleIdNum & 0xFFFFFFFFFFFFE000).zfill(16)

class Title:
	def __init__(self):
		self.id = None
		self.rightsId = None
		self.name = None
		self.isDLC = False
		self.isUpdate = False
		self.idExt = None
		self.updateId = None
		self.version = None
		self.key = None
		self.isDemo = None
		self.region = None
		self.regions = None

		self.baseId = None
		self.releaseDate = None
		self.nsuId = None
		self.category = None
		self.ratingContent = None
		self.numberOfPlayers = None
		self.rating = None
		self.developer = None
		self.publisher = None
		self.frontBoxArt = None
		self.iconUrl = None
		self.screenshots = None
		self.bannerUrl = None
		self.intro = None
		self.description = None
		self.languages = None
		self.size = 0
		self.rank = None

	def __lt__(self, other):
		if not self.name:
			return True
		if not other.name:
			return False
		return str(self.name) < str(other.name)

	def exportDict(self, isRegion=False, full=True):
		r = {}

		if isRegion:
			blacklist = ('isDLC', 'isUpdate', 'idExt', 'updateId', 'baseId', 'regions', 'rank')
		elif full:
			blacklist = ('isDLC', 'isUpdate', 'idExt', 'updateId', 'baseId')
		else:
			blacklist = ('isDLC', 'isUpdate', 'idExt', 'updateId', 'baseId', 'rightsId', 'key', 'isDemo', 'regions', 'nsuId', 'category',
						 'ratingContent', 'numberOfPlayers', 'frontBoxArt', 'intro', 'languages', 'language', 'iconUrl', 'screenshots', 'bannerUrl')

		for i in self.__dict__.keys():
			if i not in blacklist and (full or (self.__dict__[i] is not None and (i != 'size' or self.__dict__[i] > 0))):
				r[i] = self.__dict__[i]
		return r

	def loadCsv(self, line, map=['id', 'key', 'name']):
		split = line.split('|')
		for i, value in enumerate(split):
			if i >= len(map):
				Print.info('invalid map index: ' + str(i) + ', ' + str(len(map)))
				continue

			i = str(map[i])
			methodName = 'set' + i[0].capitalize() + i[1:]
			method = getattr(self, methodName, lambda x: None)
			method(value.strip())

		# self.setId(split[0].strip())
		# self.setName(split[2].strip())
		# self.setKey(split[1].strip())

	def dict(self, map=['id', 'rightsId', 'key', 'isUpdate', 'isDLC', 'isDemo', 'name', 'version', 'region']):
		r = {}
		for i in map:
			methodName = 'get' + i[0].capitalize() + i[1:]
			method = getattr(self, methodName, lambda: methodName)
			r[i] = method()
		return r

	def importFrom(self, regionTitle, region, language, preferredRegion, preferredLanguage):
		if not regionTitle.name or not regionTitle.id:
			return

		for k, v in regionTitle.__dict__.items():
			if k in ('id', 'version', 'regions', 'key'):
				continue

			if v is not None:
				setattr(self, k, v)

		self.setId(self.id)
		self.setVersion(regionTitle.version)
		self.region = region
		self.language = language

	def serialize(self, map=['id', 'rightsId', 'key', 'isUpdate', 'isDLC', 'isDemo', 'name', 'version', 'region']):
		r = []
		for i in map:

			methodName = 'get' + i[0].capitalize() + i[1:]
			method = getattr(self, methodName, lambda: methodName)
			r.append(str(method()))
		return '|'.join(r)

	def filterExt(self, lst, ext):
		if not ext:
			return lst

		n = []

		for i in lst:
			if i.path.endswith(ext):
				n.append(i)

		return n

	def getFiles(self, ext=None):
		if len(fileLUT) == 0:
			for path, f in Nsps.files.items():
				tid = f.titleId.upper()
				if tid not in fileLUT:
					fileLUT[tid] = []
				fileLUT[tid].append(f)

		if self.id in fileLUT:
			return self.filterExt(fileLUT[self.id], ext)

		return []

	def getLatestFile(self):
		highestNsp = None
		highestNsx = None

		for nsp in self.getFiles():
			try:
				if nsp.path.endswith('.nsx'):
					if not highestNsx or int(nsp.version) > int(highestNsx.version):
						highestNsx = nsp
				else:
					if not highestNsp or int(nsp.version) > int(highestNsp.version):
						highestNsp = nsp
			except BaseException:
				pass

		return highestNsp or highestNsx

	def getLatestNsp(self, version=None):
		highest = None

		for nsp in self.getFiles():
			try:
				if nsp.path.endswith('.nsp'):
					if version is not None and nsp.version == version:
						return nsp

					if not highest or int(nsp.version) > int(highest.version):
						highest = nsp
			except BaseException:
				pass

		return highest

	def getLatestNsz(self, version=None):
		highest = None

		for nsp in self.getFiles():
			try:
				if nsp.path.endswith('.nsz'):
					if version is not None and nsp.version == version:
						return nsp

					if not highest or int(nsp.version) > int(highest.version):
						highest = nsp
			except BaseException:
				pass

		return highest

	def getLatestNsx(self, version=None):
		highest = None

		for nsp in self.getFiles():
			try:
				if nsp.path.endswith('.nsx'):
					if version is not None and nsp.version == version:
						return nsp

					if not highest or int(nsp.version) > int(highest.version):
						highest = nsp
			except BaseException:
				pass

		return highest

	def getLatestXci(self, version=None):
		highest = None

		for nsp in self.getFiles():
			try:
				if nsp.path.endswith('.xci'):
					if version is not None and nsp.version == version:
						return nsp

					if not highest or int(nsp.version) > int(highest.version):
						highest = nsp
			except BaseException:
				pass

		return highest

	def isUpdateAvailable(self, localOnly=False):
		nsp = self.getLatestFile()
		if not nsp:
			if not nsp:
				if not self.isUpdate or (self.version and int(self.version) > 0):
					return True
				else:
					return False

		try:
			latest = self.lastestVersion(localOnly=localOnly)
			if latest is None:
				return False
			if int(nsp.version) < int(latest):
				return True
		except BaseException as e:
			Print.error('isUpdateAvailable exception %s: %s' % (self.id, str(e)))
			pass

		return False

	def getIsDLC(self):
		return self.isDLC*1

	def setIsDLC(self, v):
		try:
			v = int(v, 10)
			if v == 1:
				self.isDLC = True
			elif v == 0:
				self.isDLC = False
		except BaseException:
			pass

	def getRank(self):
		return self.rank*1

	def setRank(self, v):
		try:
			self.rank = int(v, 10)
		except BaseException:
			pass

	def getIsUpdate(self):
		return self.isUpdate*1

	def setIsUpdate(self, v):
		try:
			v = int(v, 10)
			if v == 1:
				self.isUpdate = True
			elif v == 0:
				self.isUpdate = False
		except BaseException:
			pass

	def getIsDemo(self):
		try:
			return self.isDemo*1
		except BaseException:
			return 0

	def setIsDemo(self, v):
		try:
			v = int(v, 10)
			if v == 1:
				self.isDemo = True
			elif v == 0:
				self.isDemo = False
		except BaseException:
			pass

	def setNsuId(self, nsuId):
		if nsuId:
			self.nsuId = int(nsuId)
			if nsuId:
				self.isDemo = str(nsuId)[0:4] == '7003'

	def setRightsId(self, rightsId):
		if not id:
			self.setId(rightsId)

		if rightsId and len(rightsId) == 32 and rightsId != '00000000000000000000000000000000':
			self.rightsId = rightsId.upper()

	def getRightsId(self):
		return self.rightsId or '00000000000000000000000000000000'

	def isBase(self):
		if self.baseId == self.id:
			return True
		else:
			return False

	def setIds(self, ids):
		for id in ids:
			self.setId(id)
			break
		self.ids = ids
		
	def addId(self, id):
		id = id.upper()
		self.setId(id)
		try:
			if id not in self.ids:
				self.ids.append(id)
		except:
			self.ids = [id]

	def setId(self, id):
		if not hasattr(self, 'rank'):
			self.rank = None

		self.isUpdate = False
		self.baseId = None
		if not id:
			return

		id = id.upper()

		try:
			i = int(id, 16)
		except BaseException:
			return

		if len(id) == 32:
			self.id = id[:16]
			self.setRightsId(id)
		elif len(id) == 16:
			self.id = id[:16]
		else:
			return

		titleIdNum = int(self.id, 16)

		if self.id:
			self.baseId = '{:02X}'.format(titleIdNum & 0xFFFFFFFFFFFFE000).zfill(16)

		self.isDLC = (titleIdNum & 0xFFFFFFFFFFFFE000) != (titleIdNum & 0xFFFFFFFFFFFFF000)
		#self.isBase = self.id == titleIdNum & 0xFFFFFFFFFFFFE000
		self.idExt = titleIdNum & 0x0000000000000FFF

		if self.isDLC:
			# dlc
			self.isUpdate = False
		elif self.idExt == 0:
			# base
			self.updateId = '%s800' % self.id[:-3]
		else:
			# update
			self.isUpdate = True
			pass

	@staticmethod
	def baseDlcId(id):
		titleIdNum = int(id, 16)

		return (titleIdNum & 0xFFFFFFFFFFFFE000) + 0x1000
		# return hex(dlcId)

	def getId(self):
		return self.id or '0000000000000000'

	def getBaseId(self):
		return self.baseId or '0000000000000000'

	def getBase(self):
		baseId = getBaseId(self.id)
		if Titles.contains(baseId):
			return Titles.get(baseId)

		return None

	def setRegion(self, region):
		if not self.region and re.match(r'[A-Z]{2}', region):
			self.region = region

	def getRegion(self):
		return self.region or ''

	def setName(self, name):
		if not name or self.name:
			return
		self.name = name

		if self.isDemo is None:
			if re.match(r'.*\s[\(\[]?Demo[\)\]]?\s*$', self.name, re.I) or re.match(r'.*\s[\(\[]?Demo[\)\]]?\s+.*$', self.name, re.I):
				self.isDemo = True
			else:
				self.isDemo = False

	def setNameOverride(self, name):
		if not name:
			return
		self.name = name

		if self.isDemo is None:
			if re.match(r'.*\s[\(\[]?Demo[\)\]]?\s*$', self.name, re.I) or re.match(r'.*\s[\(\[]?Demo[\)\]]?\s+.*$', self.name, re.I):
				self.isDemo = True
			else:
				self.isDemo = False

	def getName(self):
		baseId = getBaseId(self.id)
		if hasattr(self, 'isUpdate') and self.isUpdate and Titles.contains(baseId):
			return (Titles.get(baseId).name or '').replace('\n', ' ')
		return (self.name or '').replace('\n', ' ')

	def getBaseName(self):
		baseId = getBaseId(self.id)
		if Titles.contains(baseId):
			return (Titles.get(baseId).name or '').replace('\n', ' ')
		return ''

	def setKey(self, key):
		if not key:
			return

		key = key.upper()

		if len(key) != 32:
			return

		try:
			i = int(key, 16)

			if i <= 0:
				return
		except BaseException:
			return

		self.key = key

	def getKey(self):
		return self.key or '00000000000000000000000000000000'

	def setVersion(self, version, force=False):
		if version is not None:
			try:
				n = int(str(version), 10)
			except BaseException:
				return

			try:
				o = int(str(self.version), 10)
			except BaseException:
				o = None

			if not o or n > o or force:
				self.version = n

	def getVersion(self):
		if self.version is None:
			return ''
		return self.version

	def setParentId(self, titleId):
		try:
			self.parentId = titleId
		except BaseException:
			pass

	def lastestVersion(self, force=False, localOnly=False):
		# if self.isDLC:
		#	return '0'

		try:

			if not self.id:
				return None

			if (self.version is None or force) and (not localOnly):
				self.version = cdn.version(self.id)
				Print.info('Grabbed %s [%s] version, %s' % (str(self.name), str(self.id), str(self.version)))

			#Print.info('version: ' + str(self.version))
			return self.version
		except BaseException as e:
			Print.error(str(e))
			return None

	def isValid(self):
		if self.id:
			return True
		else:
			return False

	def isActive(self, skipKeyCheck=False):
		if self.id[0:13] == '0100000000000':
			return False

		base = self

		if self.isDLC or self.isUpdate:
			baseId = getBaseId(self.id)
			if Titles.contains(baseId):
				base = Titles.get(baseId)

		if (self.isDLC or self.isUpdate or Config.download.base) and (not self.isDLC or Config.download.DLC) and (not base.isDemo or Config.download.demo) and (not self.isUpdate or Config.download.update) and (
				base.key or Config.download.sansTitleKey or self.isUpdate or skipKeyCheck) and (len(Config.titleWhitelist) == 0 or self.id in Config.titleWhitelist) and self.id not in Config.titleBlacklist:
			if Config.shardIndex is not None and Config.shardCount is not None:
				if (int(self.id[0:13], 16) // 2) % Config.shardCount != Config.shardIndex:
					return False

			if Config.download.rankMin is not None:
				if base.rank is None or base.rank < Config.download.rankMin:
					return False

			if Config.download.rankMax is not None:
				if base.rank is None or base.rank > Config.download.rankMax:
					return False

			if Config.download.regions is not None and len(Config.download.regions) > 0:
				if not Config.download.hasRegion(base.regions):
					return False

			return True
		else:
			return False

	@staticmethod
	def getCdnVersion(id):
		r = cdn.version(id)

		# if len(r) == 0 or r[0] == 'none':
		#	return ['0']

		return r

	def download(self, base, fileName, url):
		path = os.path.join(base, fileName)
		if os.path.isfile(path):
			return path
		os.makedirs(base, exist_ok=True)
		urllib.request.urlretrieve(url, path)
		return path

	def getResizedImage(self, filePath, width=None, height=None):
		if not width and not height:
			return filePath

		base, name = os.path.split(filePath)
		path = os.path.join(base, '.' + str(width) + 'x' + str(height) + '_' + name)

		if not os.path.isfile(path):
			os.makedirs(base, exist_ok=True)
			im = Image.open(filePath)
			ar = im.size[0] / im.size[1]
			if height is None:
				height = int(width / ar)
			elif width is None:
				width = int(height * ar)

			out = im.resize((width, height), Image.Resampling.LANCZOS)
			out.save(path, quality=100)

		return path

	def bannerFile(self, width=None, height=None):
		if not self.bannerUrl or self.bannerUrl.startswith('cocoon:/'):
			return None

		baseName, ext = os.path.splitext(self.bannerUrl)
		return self.getResizedImage(self.download(Config.paths.titleImages + self.id, 'banner' + ext, self.bannerUrl), width, height)

	def frontBoxArtFile(self, width=None, height=None):
		if not self.frontBoxArt or self.frontBoxArt.startswith('cocoon:/'):
			return None

		baseName, ext = os.path.splitext(self.frontBoxArt)
		return self.getResizedImage(self.download(Config.paths.titleImages + self.id, 'frontBoxArt' + ext, self.frontBoxArt), width, height)

	def iconFile(self, width=None, height=None):
		if 'iconUrl' not in self.__dict__:
			self.iconUrl = None

		if not self.iconUrl or self.iconUrl.startswith('cocoon:/'):
			return None

		baseName, ext = os.path.splitext(self.iconUrl)
		return self.getResizedImage(self.download(Config.paths.titleImages + self.id, 'icon' + ext, self.iconUrl), width, height)

	def screenshotFile(self, i, width=None, height=None):
		if not self.screenshots[i] or self.screenshots[i].startswith('cocoon:/'):
			return None

		baseName, ext = os.path.splitext(self.screenshots[i])
		return self.getResizedImage(self.download(Config.paths.titleImages + self.id, 'screenshot' + str(i) + ext, self.screenshots[i]), width, height)

	def screenshotFiles(self):
		if not self.screenshots:
			return []
		r = []
		for i, u in enumerate(self.screenshots):
			r.append(self.screenshotFile(i))
		return r

	def parseShogunJson(self, _json, region=None, language=None, canGrabFromShogun=False):
		if not _json:
			return None

		if 'hero_banner_url' in _json:
			self.bannerUrl = _json['hero_banner_url']

		if "release_date_on_eshop" in _json:
			try:
				self.releaseDate = int(_json["release_date_on_eshop"].replace('-', ''))
			except BaseException:
				pass

		'''
		if "id" in _json:
			try:
				self.setNsuId("%s" % _json["id"])
			except BaseException as e:
				Print.info('error setting nsuid: ' + str(e))
				pass
		'''

		if "formal_name" in _json:
			self.name = _json["formal_name"].strip()

		if 'screenshots' in _json:
			self.screenshots = []
			for i, k in enumerate(_json["screenshots"]):
				self.screenshots.append(k["images"][0]["url"])

		if "languages" in _json:
			self.languages = []
			for language in _json["languages"]:
				self.languages.append(language['iso_code'])

		if "genre" in _json:
			self.category = _json["genre"].split(' / ')

		if "total_rom_size" in _json:
			self.size = _json["total_rom_size"]

		if "rating_info" in _json:
			if "rating" in _json["rating_info"]:
				if "age" in _json["rating_info"]['rating']:
					self.rating = _json["rating_info"]['rating']['age']

			if "content_descriptors" in _json["rating_info"]:
				content = []
				for descriptor in _json["rating_info"]["content_descriptors"]:
					content.append(descriptor['name'])
				self.ratingContent = content

		if "player_number" in _json:
			if 'local_max' in _json["player_number"]:
				self.numberOfPlayers = _json["player_number"]["local_max"]

			if 'offline_max' in _json["player_number"]:
				self.numberOfPlayers = _json["player_number"]["offline_max"]

		if "publisher" in _json:
			if 'name' in _json["publisher"]:
				self.publisher = _json["publisher"]["name"]
			if 'title' in _json["publisher"]:
				self.publisher = _json["publisher"]["title"]

		if "applications" in _json and isinstance(_json["applications"], list):
			for a in _json["applications"]:
				'''
				if "id" in a:
								self.setId(a['id'])
				'''

				if "image_url" in a:
					self.iconUrl = a['image_url']
				break

		if "applications" in _json and "image_url" in _json["applications"]:
			self.iconUrl = _json["applications"]['image_url']

		if "catch_copy" in _json:
			#self.intro = htmlToText(_json["catch_copy"])
			self.intro = _json["catch_copy"]

		if "description" in _json:
			#self.description = htmlToText(_json["description"])
			self.description = _json["description"]

		try:
			if "target_titles" in _json:
				for nsu in _json["target_titles"]:
					if not Titles.hasNsuid(nsu["id"], region, language):
						if canGrabFromShogun:
							baseTitle = Titles.getNsuid(nsu["id"], region, language)
							baseTitle.parseShogunJson(cdn.Shogun.getTitleByNsuid(nsu["id"], region, language), region, language, True)
							#Titles.saveRegion(region, language)
					else:
						baseTitle = Titles.getNsuid(nsu["id"], region, language)
						if baseTitle.id:
							pass
							# self.setId(baseTitle.id)
							#Print.info("setting appid " + str(baseTitle.id))
						# else:
						#	Print.error("Could not find title for " + str(nsu["id"]))
		except BaseException:
			Print.error('target titles error')
			raise

	def scrape(self, delta=True):
		if self.isUpdate or self.isDLC:
			return
		try:
			if (not delta or not self.bannerUrl):
				id = self.id

				cookies = {'esrb.verified': 'true'}
				for region in ['JP', 'AU']:
					result = grabCachedRedirectUrl("https://ec.nintendo.com/apps/%s/%s" % (id, region), cookies=cookies)
					_json = ''
					if not result or result.status_code != 200:
						continue

					_json = json.loads(result.text.split('NXSTORE.titleDetail.jsonData = ')[1].split('NXSTORE.titleDetail')[0].replace(';', ''))

					if _json == '' or _json is None:
						Print.error('Failed to parse json for ' + "https://ec.nintendo.com/apps/%s/%s" % (id, region))
						continue

					self.parseShogunJson(_json, region)

				# <img aria-hidden="true" data-src="https://media.nintendo.com/nintendo/bin/ZppwWK6BnjH5twBNvE5wEEI9aeMGR0XX/hQGr97SGMnlXBWoqOBtgtGX5noK3tNtD.jpg"/>
				result = grabCachedRedirectUrl("https://ec.nintendo.com/apps/%s/US" % id, cookies=cookies)
				if result and result.status_code == 200:
					if result.url != 'https://www.nintendo.com/games/':
						soup = BeautifulSoup(result.text, "html.parser")

						if not self.bannerUrl:
							m = re.search(r"#hero\s*{\s*background(-image)?:\s*url\('([^)]+)'\)",
										  result.text, re.DOTALL | re.UNICODE | re.MULTILINE | re.IGNORECASE)
							if m:
								banner = m.group(2)
								if banner[0] == '/':
									banner = 'https://www.nintendo.com' + banner
								self.bannerUrl = banner

						rem = re.finditer('<img aria-hidden="true" data-src="([^"]+)"', result.text)
						if rem:
							ss = []
							for m in rem:
								ss.append(m.group(1))

							if len(ss) > 0:
								self.screenshots = ss

						if soup.find("meta", {"property": "og:url"}) is not None:
							slug = soup.find("meta", {"property": "og:url"})["content"].split('/')[-1]
							infoJson = json.loads(requests.get("https://www.nintendo.com/json/content/get/game/%s" % slug, cookies=cookies).text)["game"]

							if "release_date" in infoJson:
								self.releaseDate = int(datetime.datetime.strftime(datetime.datetime.strptime(infoJson["release_date"], "%b %d, %Y"), '%Y%m%d'))

							if "name" in infoJson:
								self.name = infoJson["name"].strip()

							if "nsuid" in infoJson:
								self.setNsuId(int(infoJson["nsuid"]))

							catagories = []
							if "game_category_ref" in infoJson:
								catindex = 0
								if "name" in infoJson["game_category_ref"]:
									catagories.append(infoJson["game_category_ref"]["name"])
								elif "title" in infoJson["game_category_ref"]:
									catagories.append(infoJson["game_category_ref"]["title"])
								else:
									try:
										for game_category in infoJson["game_category_ref"]:
											catagories.append(infoJson["game_category_ref"][catindex]["name"])
											catindex += 1
									except BaseException:
										pass
								self.category = catagories

							esrbcontent = []
							if "esrb_content_descriptor_ref" in infoJson:
								esrbindex = 0
								if "name" in infoJson["esrb_content_descriptor_ref"]:
									esrbcontent.append(infoJson["esrb_content_descriptor_ref"]["name"])
								elif "title" in infoJson["esrb_content_descriptor_ref"]:
									esrbcontent.append(infoJson["esrb_content_descriptor_ref"]["title"])
								else:
									try:
										for descriptor in infoJson["esrb_content_descriptor_ref"]:
											if 'name' in descriptor:
												esrbcontent.append(descriptor["name"])
											if 'title' in descriptor:
												esrbcontent.append(descriptor["title"])
									except BaseException:
										pass
								self.ratingContent = esrbcontent

							if "number_of_players" in infoJson:
								self.numberOfPlayers = re.sub(r'[^0-9]', '', infoJson["number_of_players"])

							if "esrb_rating_ref" in infoJson:
								if "esrb_rating" in infoJson["esrb_rating_ref"]:
									if "short_description" in infoJson["esrb_rating_ref"]["esrb_rating"]:
										self.rating = infoJson["esrb_rating_ref"]["esrb_rating"]["short_description"]

							'''
							if not self.screenshots:
								try:
									ss = []
									for s in infoJson["screenshot_gallery_ref"]["screenshot_gallery"]["screenshots"]:
										ss.append(s['image']['large_image']['include']['src'].replace('cocoon:/', ''))
									self.screenshots = ss
								except:
									pass
							'''

							if "developer_ref" in infoJson:
								if "name" in infoJson["developer_ref"]:
									self.developer = infoJson["developer_ref"]["name"]

							if "publisher_ref" in infoJson:
								if "name" in infoJson["publisher_ref"]:
									self.publisher = infoJson["publisher_ref"]["name"]
								if 'title' in infoJson["publisher_ref"]:
									self.publisher = infoJson["publisher_ref"]["title"]

							if "front_box_art" in infoJson:
								if "image" in infoJson["front_box_art"]:
									if "image" in infoJson["front_box_art"]["image"]:
										if "url" in infoJson["front_box_art"]["image"]["image"]:
											self.frontBoxArt = infoJson["front_box_art"]["image"]["image"]["url"]

							if "intro" in infoJson:
								try:
									details = BeautifulSoup(infoJson["intro"][0], "html.parser")
									try:
										details = details.decode(formatter=None)
									except BaseException:
										details = details.decode()
									details = re.sub(r'<[^<]+?>', '', details).strip()
									details = re.sub(r' +', ' ', details)
									details = re.sub(r'\n ', '\n', details)
									details = re.sub(r'\n\n+', '\n\n', details)
									details = re.sub(r'(?<!\n)\n(?!\n)', ' ', details)
									details = re.sub(r'  ', ' ', details)
									self.intro = details
								except Exception as e:
									pass

							if "game_overview_description" in infoJson:
								details = BeautifulSoup(infoJson["game_overview_description"][0], "html.parser")
								try:
									details = details.decode(formatter=None)
								except BaseException:
									details = details.decode()
								details = re.sub(r'<[^<]+?>', '', details).strip()
								details = re.sub(r' +', ' ', details)
								details = re.sub(r'\n ', '\n', details)
								details = re.sub(r'\n\n+', '\n\n', details)
								details = re.sub(r'(?<!\n)\n(?!\n)', ' ', details)
								details = re.sub(r'  ', ' ', details)
								self.description = details
				# else:
					#f = open("missing.txt", 'a', encoding="utf8")
					#f.write(rid+"|title doesn't exist at ec.nintendo.com"+'\n')
					# f.close()

		except BaseException as e:
			pass
			print(repr(e) + ' ' + self.id)
			traceback.print_exc(file=sys.stdout)
			raise

		self.bannerFile()
		self.frontBoxArtFile()
		self.iconFile()
		self.screenshotFiles()
