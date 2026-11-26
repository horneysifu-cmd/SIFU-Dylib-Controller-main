#import "SIFULoginManager.h"
#import "SIFULicenseViewController.h"

@implementation SIFULoginManager

+ (instancetype)shared {
    static SIFULoginManager *manager;
    static dispatch_once_t onceToken;
    dispatch_once(&onceToken, ^{
        manager = [SIFULoginManager new];
    });
    return manager;
}

- (void)presentLicenseGateFromViewController:(UIViewController *)host {
    NSAssert(NSThread.isMainThread, @"Present the SIFU gate on the main thread");
    if (!host || host.presentedViewController) return;

    SIFULicenseViewController *gate = [SIFULicenseViewController new];
    gate.modalPresentationStyle = UIModalPresentationFullScreen;
    gate.modalTransitionStyle = UIModalTransitionStyleCrossDissolve;
    [host presentViewController:gate animated:NO completion:nil];
}

@end
