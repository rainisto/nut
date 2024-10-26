# -*- coding: utf-8 -*-
import socket

from PyQt5.QtCore import (Qt, QTimer)
from PyQt5.QtWidgets import (QVBoxLayout, QHBoxLayout, QPushButton, QLabel)

from nut import Config, Users, Usb
from translator import tr

def _get_ip_address():
	s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	try:
		s.connect(("8.8.8.8", 80))
		ip = s.getsockname()[0]
		s.close()
		return ip
	except OSError:
		return None

def _get_ipv6_address():
	s = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
	try:
		s.connect(("2001:db8::", 1027))
		ip = s.getsockname()[0]
		s.close()
		return ip
	except OSError:
		return None

def _create_button(app, parent, text, max_width, handler):
	widget = QPushButton(text, app)
	widget.setMaximumWidth(max_width)
	widget.clicked.connect(handler)
	widget.setFocusPolicy(Qt.StrongFocus)
	parent.addWidget(widget)
	return widget

class Header: # pylint: disable=too-many-instance-attributes,too-few-public-methods
	def __init__(self, app):
		self.layout = QVBoxLayout()

		top = QHBoxLayout()
		bottom = QHBoxLayout()

		self.scan = _create_button(app, top, tr('main.top_menu.scan'), 100, app.on_scan)
		if Config.allow_organize:
			_create_button(app, top, tr('main.top_menu.organize'), 200, app.on_organize)

		if Config.allow_pull:
			self.pull = _create_button(app, top, tr('main.top_menu.pull'), 100, app.on_pull)

		self.titledb = _create_button(app, top, tr('main.top_menu.update_titledb'), 200, app.on_titledb)

		if Config.allow_decompress:
			_create_button(app, top, tr('main.top_menu.decompress_nsz'), 200, app.on_decompress)

		if Config.allow_compress:
			_create_button(app, top, tr('main.top_menu.compress_nsp'), 200, app.on_compress)

		if Config.allow_gdrive:
			self.gdrive = _create_button(app, top, tr('main.top_menu.setup_gdrive'), 200, app.on_gdrive)

		top.addStretch()

		ipAddr = _get_ip_address()
		ipv6Addr = _get_ipv6_address()

		if ipAddr or ipv6Addr:
			if Config.server.hostname == "::":
				self.serverInfo = QLabel(
				f"<b>{tr('main.status.ip')}v4:</b>  {ipAddr}  <b>{tr('main.status.ip')}v6:</b>  {ipv6Addr}  <b>{tr('main.status.port')}:</b>  {Config.server.port}  " +
				f"<b>{tr('main.status.user')}:</b>  {Users.first().id}  <b>{tr('main.status.password')}:</b>  " +
				f"{Users.first().password}"
				)
			else:
				self.serverInfo = QLabel(
					f"<b>{tr('main.status.ip')}:</b>  {ipAddr}  <b>{tr('main.status.port')}:</b>  {Config.server.port}  " +
					f"<b>{tr('main.status.user')}:</b>  {Users.first().id}  <b>{tr('main.status.password')}:</b>  " +
					f"{Users.first().password}"
				)
		else:
			self.serverInfo = QLabel("<b>Offline</b>")

		self.serverInfo.setMinimumWidth(200)
		self.serverInfo.setAlignment(Qt.AlignCenter)
		bottom.addWidget(self.serverInfo)
		bottom.addStretch()

		self.usbStatus = QLabel("<b>USB:</b>  " + tr("usb.status." + Usb.status))
		self.usbStatus.setMinimumWidth(50)
		self.usbStatus.setAlignment(Qt.AlignCenter)
		bottom.addWidget(self.usbStatus)

		self.timer = QTimer()
		self.timer.setInterval(1000)
		self.timer.timeout.connect(self.tick)
		self.timer.start()

		self.layout.addLayout(top)
		self.layout.addLayout(bottom)

	def tick(self):
		self.usbStatus.setText("<b>USB:</b> " + tr("usb.status." + Usb.status))
