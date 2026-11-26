#import <UIKit/UIKit.h>

NS_ASSUME_NONNULL_BEGIN

@interface SIFULoginManager : NSObject
+ (instancetype)shared;
- (void)presentLicenseGateFromViewController:(UIViewController *)host;
@end

NS_ASSUME_NONNULL_END
