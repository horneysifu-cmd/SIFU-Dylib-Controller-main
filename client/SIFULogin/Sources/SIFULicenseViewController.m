#import "SIFULicenseViewController.h"
#import <Security/Security.h>

static NSString * const SIFUAPIBase = @"https://controller.160-236-59-174.sslip.io";
static NSString * const SIFUKeychainService = @"com.sifu.license";
static NSString * const SIFUKeychainAccount = @"license-key";

@interface SIFULicenseViewController ()
@property (nonatomic, strong) UITextField *keyField;
@property (nonatomic, strong) UILabel *statusLabel;
@property (nonatomic, strong) UIButton *activateButton;
@property (nonatomic) BOOL requestInFlight;
@end

@implementation SIFULicenseViewController

- (void)viewDidLoad {
    [super viewDidLoad];
    self.view.backgroundColor = [UIColor colorWithRed:0.035 green:0.043 blue:0.07 alpha:1.0];
    [self buildUI];

    NSString *savedKey = [self savedLicenseKey];
    if (savedKey.length) {
        self.keyField.text = savedKey;
        [self validateKey:savedKey endpoint:@"/api/license/validate" saveOnSuccess:NO];
    }
}

- (void)buildUI {
    UILabel *brand = [UILabel new];
    brand.text = @"SIFU";
    brand.font = [UIFont systemFontOfSize:38 weight:UIFontWeightBlack];
    brand.textColor = UIColor.whiteColor;
    brand.textAlignment = NSTextAlignmentCenter;

    UILabel *subtitle = [UILabel new];
    subtitle.text = @"LICENSE ACTIVATION";
    subtitle.font = [UIFont systemFontOfSize:13 weight:UIFontWeightSemibold];
    subtitle.textColor = [UIColor colorWithWhite:0.72 alpha:1];
    subtitle.textAlignment = NSTextAlignmentCenter;

    self.keyField = [UITextField new];
    self.keyField.placeholder = @"Enter your license key";
    self.keyField.autocapitalizationType = UITextAutocapitalizationTypeAllCharacters;
    self.keyField.autocorrectionType = UITextAutocorrectionTypeNo;
    self.keyField.clearButtonMode = UITextFieldViewModeWhileEditing;
    self.keyField.borderStyle = UITextBorderStyleRoundedRect;
    self.keyField.backgroundColor = UIColor.whiteColor;
    self.keyField.textColor = UIColor.blackColor;
    self.keyField.returnKeyType = UIReturnKeyGo;
    self.keyField.translatesAutoresizingMaskIntoConstraints = NO;

    self.activateButton = [UIButton buttonWithType:UIButtonTypeSystem];
    [self.activateButton setTitle:@"ACTIVATE LICENSE" forState:UIControlStateNormal];
    self.activateButton.titleLabel.font = [UIFont systemFontOfSize:16 weight:UIFontWeightBold];
    [self.activateButton setTitleColor:UIColor.whiteColor forState:UIControlStateNormal];
    self.activateButton.backgroundColor = [UIColor colorWithRed:0.12 green:0.38 blue:0.95 alpha:1];
    self.activateButton.layer.cornerRadius = 12;
    [self.activateButton addTarget:self action:@selector(activateTapped) forControlEvents:UIControlEventTouchUpInside];
    self.activateButton.translatesAutoresizingMaskIntoConstraints = NO;

    self.statusLabel = [UILabel new];
    self.statusLabel.text = @"Enter the license key provided by SIFU.";
    self.statusLabel.textColor = [UIColor colorWithWhite:0.78 alpha:1];
    self.statusLabel.font = [UIFont systemFontOfSize:13];
    self.statusLabel.textAlignment = NSTextAlignmentCenter;
    self.statusLabel.numberOfLines = 0;
    self.statusLabel.translatesAutoresizingMaskIntoConstraints = NO;

    UIStackView *stack = [[UIStackView alloc] initWithArrangedSubviews:@[brand, subtitle, self.keyField, self.activateButton, self.statusLabel]];
    stack.axis = UILayoutConstraintAxisVertical;
    stack.spacing = 18;
    stack.alignment = UIStackViewAlignmentFill;
    stack.translatesAutoresizingMaskIntoConstraints = NO;
    [self.view addSubview:stack];

    [NSLayoutConstraint activateConstraints:@[
        [stack.centerYAnchor constraintEqualToAnchor:self.view.centerYAnchor],
        [stack.leadingAnchor constraintEqualToAnchor:self.view.leadingAnchor constant:28],
        [stack.trailingAnchor constraintEqualToAnchor:self.view.trailingAnchor constant:-28],
        [self.keyField.heightAnchor constraintEqualToConstant:52],
        [self.activateButton.heightAnchor constraintEqualToConstant:52]
    ]];
}

- (void)activateTapped {
    NSString *key = [self.keyField.text stringByTrimmingCharactersInSet:NSCharacterSet.whitespaceAndNewlineCharacterSet];
    if (key.length < 6) {
        self.statusLabel.text = @"Please enter a valid license key.";
        return;
    }
    [self validateKey:key endpoint:@"/api/license/activate" saveOnSuccess:YES];
}

- (NSString *)deviceReference {
    NSString *value = UIDevice.currentDevice.identifierForVendor.UUIDString;
    return value.length ? value : NSUUID.UUID.UUIDString;
}

- (void)validateKey:(NSString *)key endpoint:(NSString *)endpoint saveOnSuccess:(BOOL)save {
    if (self.requestInFlight) return;
    self.requestInFlight = YES;
    self.activateButton.enabled = NO;
    self.statusLabel.text = @"Contacting SIFU license server…";

    NSURL *url = [NSURL URLWithString:[SIFUAPIBase stringByAppendingString:endpoint]];
    NSMutableURLRequest *request = [NSMutableURLRequest requestWithURL:url
                                                           cachePolicy:NSURLRequestReloadIgnoringLocalCacheData
                                                       timeoutInterval:20.0];
    request.HTTPMethod = @"POST";
    [request setValue:@"application/json" forHTTPHeaderField:@"Content-Type"];
    request.HTTPBody = [NSJSONSerialization dataWithJSONObject:@{
        @"license_key": key,
        @"device_ref": [self deviceReference]
    } options:0 error:nil];

    NSURLSessionDataTask *task = [[NSURLSession sharedSession] dataTaskWithRequest:request
        completionHandler:^(NSData *data, NSURLResponse *response, NSError *error) {
        NSDictionary *json = nil;
        if (data) {
            id parsed = [NSJSONSerialization JSONObjectWithData:data options:0 error:nil];
            if ([parsed isKindOfClass:NSDictionary.class]) json = parsed;
        }
        NSInteger statusCode = [(NSHTTPURLResponse *)response statusCode];
        BOOL valid = !error && statusCode >= 200 && statusCode < 300 && [json[@"valid"] respondsToSelector:@selector(boolValue)] && [json[@"valid"] boolValue];

        dispatch_async(dispatch_get_main_queue(), ^{
            self.requestInFlight = NO;
            self.activateButton.enabled = YES;
            if (valid) {
                if (save) [self saveLicenseKey:key];
                self.statusLabel.text = @"License verified. Unlocking…";
                [self dismissViewControllerAnimated:YES completion:nil];
            } else {
                NSString *serverMessage = [json[@"detail"] isKindOfClass:NSString.class] ? json[@"detail"] : nil;
                self.statusLabel.text = serverMessage ?: (error ? @"Network error. Please try again." : @"License invalid, expired, blocked, or not authorized for this device.");
            }
        });
    }];
    [task resume];
}

#pragma mark - Keychain

- (NSString *)savedLicenseKey {
    NSDictionary *query = @{
        (__bridge id)kSecClass: (__bridge id)kSecClassGenericPassword,
        (__bridge id)kSecAttrService: SIFUKeychainService,
        (__bridge id)kSecAttrAccount: SIFUKeychainAccount,
        (__bridge id)kSecReturnData: @YES,
        (__bridge id)kSecMatchLimit: (__bridge id)kSecMatchLimitOne
    };
    CFTypeRef result = NULL;
    OSStatus status = SecItemCopyMatching((__bridge CFDictionaryRef)query, &result);
    if (status != errSecSuccess || !result) return nil;
    NSData *data = CFBridgingRelease(result);
    return [[NSString alloc] initWithData:data encoding:NSUTF8StringEncoding];
}

- (void)saveLicenseKey:(NSString *)key {
    NSData *data = [key dataUsingEncoding:NSUTF8StringEncoding];
    NSDictionary *base = @{
        (__bridge id)kSecClass: (__bridge id)kSecClassGenericPassword,
        (__bridge id)kSecAttrService: SIFUKeychainService,
        (__bridge id)kSecAttrAccount: SIFUKeychainAccount
    };
    SecItemDelete((__bridge CFDictionaryRef)base);
    NSMutableDictionary *item = [base mutableCopy];
    item[(__bridge id)kSecValueData] = data;
    item[(__bridge id)kSecAttrAccessible] = (__bridge id)kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly;
    SecItemAdd((__bridge CFDictionaryRef)item, NULL);
}

@end
