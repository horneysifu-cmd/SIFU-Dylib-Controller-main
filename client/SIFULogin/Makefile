ARCHS = arm64
TARGET = iphone:clang:latest:13.0

include $(THEOS)/makefiles/common.mk

LIBRARY_NAME = SIFULogin
SIFULogin_FILES = Sources/SIFULoginManager.m Sources/SIFULicenseViewController.m
SIFULogin_FRAMEWORKS = UIKit Foundation Security
SIFULogin_CFLAGS = -fobjc-arc
SIFULogin_INSTALL_PATH = /usr/lib

include $(THEOS_MAKE_PATH)/library.mk
