# SIFULogin Dylib (authorized host apps)

This project builds an ARM64 iOS dynamic library with Theos on Linux/Debian. It is a license UI component for an app that you own or are authorized to modify; it is not a universal IPA injector.

## Build on Debian

Install Theos using its official Linux installer as a normal user (not root):

```sh
sudo apt update
sudo apt install -y bash curl sudo
bash -c "$(curl -fsSL https://raw.githubusercontent.com/theos/theos/master/bin/install-theos)"
export THEOS="$HOME/theos"
cd client/SIFULogin
make
```

The official installer provisions Theos, its iOS toolchain and SDK. If you open a new terminal, run `export THEOS="$HOME/theos"` again or add it to your shell profile.

## GitHub Actions

Pushing changes under this directory triggers the Linux build workflow. The resulting `SIFULogin.dylib` is uploaded as a workflow artifact.

## Host integration

The host app must explicitly load/link the library and call:

```objc
#import "SIFULoginManager.h"
[[SIFULoginManager shared] presentLicenseGateFromViewController:self];
```

Call it from the host app's first screen on the main thread, and keep that app's protected features behind the gate. Copying a dylib into an IPA does not make iOS load it automatically. Signing, loader configuration, ABI compatibility and host-app integration are separate requirements.

## API

The current client expects:
- Base URL: `https://controller.160-236-59-174.sslip.io`
- `POST /api/license/activate`
- `POST /api/license/validate`
- JSON body: `license_key`, `device_ref`
- JSON success: `valid: true`

Confirm the deployed API response contract before distributing. The dashboard admin token/password is never embedded in this client. Offline or failed requests do not unlock the protected feature.
