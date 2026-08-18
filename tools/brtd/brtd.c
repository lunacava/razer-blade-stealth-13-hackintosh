/*
 * brtd -- make the Razer Blade Stealth 13 brightness keys work under macOS.
 *
 * WHY THIS EXISTS (all measured on this machine, 2026-08-18):
 *   The keys are fine.  Pressing them collapses IOHIDSystem's HIDIdleTime
 *   from 78 s to 0.1 s, and a hidutil identification probe showed they send
 *   the standard usages: Consumer 0x70 = Display Brightness Decrement and
 *   Consumer 0x6F = Display Brightness Increment.
 *
 *   macOS simply does not act on those usages here:
 *     - hidutil UserKeyMapping cannot help.  Remapping them to
 *       AppleVendorTopCase 0x04/0x05, and to Keyboard F14, both left bklt
 *       unchanged -- while the same mechanism demonstrably worked for the
 *       source side (volume down remapped to 'z' typed a 'z').
 *     - There is no ACPI route either, so BrightnessKeys.kext would be inert:
 *       DSDT defines Method (BRTN) but nothing in the whole 60k-line table
 *       ever calls it, and no EC _Qxx sends Notify(..., 0x86/0x87).
 *
 *   Backlight *control* works: IODisplaySetFloatParameter on "bklt" returns
 *   KERN_SUCCESS and moves ioreg's bklt (0..65535).  So only the wiring from
 *   key event to that call is missing.  This program is that wire.
 *
 * SCOPE LIMITING (deliberate):
 *   Input Monitoring is an all-keystrokes permission, so narrow what we ask
 *   the HID stack to hand us:
 *     - device matching     -> VendorID 0x1532 only (the internal keyboard)
 *     - input value matching-> UsagePage 0x0C only (consumer/media keys)
 *   Letter keys live on UsagePage 0x07 and therefore never reach on_value().
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <dlfcn.h>
#include <IOKit/IOKitLib.h>
#include <IOKit/hid/IOHIDLib.h>
#include <IOKit/graphics/IOGraphicsLib.h>
#include <CoreFoundation/CoreFoundation.h>

/* Not in the Command Line Tools SDK headers; resolved at runtime.
   IOHIDRequestType: 0 = ListenEvent.  IOHIDAccessType: 0 granted, 1 denied,
   2 unknown. */
typedef int           (*chk_fn)(int);
typedef unsigned char (*req_fn)(int);

#define RAZER_VENDOR_ID 0x1532
#define CONSUMER_PAGE   0x0C
#define CSMR_BRIGHT_INC 0x6F
#define CSMR_BRIGHT_DEC 0x70

static int   gVerbose = 0;
static float gStep    = 1.0f / 16.0f;   /* Apple's 16 brightness notches */

static CFDictionaryRef dict1(const char *key, int value) {
    CFStringRef k = CFStringCreateWithCString(NULL, key, kCFStringEncodingUTF8);
    CFNumberRef v = CFNumberCreate(NULL, kCFNumberIntType, &value);
    CFDictionaryRef d = CFDictionaryCreate(NULL, (const void **)&k,
                                           (const void **)&v, 1,
                                           &kCFTypeDictionaryKeyCallBacks,
                                           &kCFTypeDictionaryValueCallBacks);
    CFRelease(k); CFRelease(v);
    return d;
}

static void nudge(float delta) {
    io_service_t svc = IOServiceGetMatchingService(kIOMainPortDefault,
                           IOServiceMatching("IODisplayConnect"));
    if (!svc) { fprintf(stderr, "no IODisplayConnect\n"); fflush(stderr); return; }
    float cur = 1.0f;
    IODisplayGetFloatParameter(svc, kNilOptions, CFSTR("bklt"), &cur);
    float want = cur + delta;
    if (want < 0.0f) want = 0.0f;
    if (want > 1.0f) want = 1.0f;
    kern_return_t kr = IODisplaySetFloatParameter(svc, kNilOptions,
                                                  CFSTR("bklt"), want);
    printf("brightness %.4f -> %.4f (kr=0x%x)\n", cur, want, kr);
    fflush(stdout);
    IOObjectRelease(svc);
}

static void on_value(void *ctx, IOReturn r, void *sender, IOHIDValueRef val) {
    (void)ctx; (void)r; (void)sender;
    IOHIDElementRef e = IOHIDValueGetElement(val);
    uint32_t page = IOHIDElementGetUsagePage(e);
    uint32_t use  = IOHIDElementGetUsage(e);
    CFIndex  v    = IOHIDValueGetIntegerValue(val);
    if (gVerbose && v) {
        printf("EVENT page=0x%02x usage=0x%02x value=%ld\n",
               page, use, (long)v);
        fflush(stdout);
    }
    if (!v) return;                    /* key-up */
    if (page != CONSUMER_PAGE) return; /* belt and braces; matching already did this */
    if (use == CSMR_BRIGHT_INC)      nudge(+gStep);
    else if (use == CSMR_BRIGHT_DEC) nudge(-gStep);
}

int main(int argc, char **argv) {
    for (int i = 1; i < argc; i++)
        if (!strcmp(argv[i], "-v")) gVerbose = 1;

    chk_fn chk = (chk_fn)dlsym(RTLD_DEFAULT, "IOHIDCheckAccess");
    if (chk) printf("IOHIDCheckAccess(ListenEvent) = %d "
                    "(0=granted 1=denied 2=unknown)\n", chk(0));
    fflush(stdout);

    IOHIDManagerRef m = IOHIDManagerCreate(kCFAllocatorDefault,
                                           kIOHIDOptionsTypeNone);
    if (!m) { fprintf(stderr, "IOHIDManagerCreate failed\n"); return 1; }

    CFDictionaryRef devMatch = dict1("VendorID", RAZER_VENDOR_ID);
    IOHIDManagerSetDeviceMatching(m, devMatch);
    CFRelease(devMatch);

    CFDictionaryRef valMatch = dict1("UsagePage", CONSUMER_PAGE);
    IOHIDManagerSetInputValueMatching(m, valMatch);
    CFRelease(valMatch);

    IOHIDManagerRegisterInputValueCallback(m, on_value, NULL);
    IOHIDManagerScheduleWithRunLoop(m, CFRunLoopGetCurrent(),
                                    kCFRunLoopDefaultMode);

    /* TCC (Input Monitoring) gates IOHIDManagerOpen and does not signal us
       when the user approves, so ask once and keep retrying.  After 20 tries
       exit non-zero and let launchd's KeepAlive give us a fresh process --
       TCC grants are picked up reliably on a new launch. */
    req_fn req = (req_fn)dlsym(RTLD_DEFAULT, "IOHIDRequestAccess");
    IOReturn kr = kIOReturnError;
    for (int i = 0; i < 20; i++) {
        kr = IOHIDManagerOpen(m, kIOHIDOptionsTypeNone);
        if (kr == kIOReturnSuccess) break;
        if (i == 0) {
            printf("IOHIDManagerOpen failed 0x%x -- requesting "
                   "Input Monitoring access\n", kr);
            fflush(stdout);
            if (req) req(0);
        }
        sleep(3);
    }
    printf("IOHIDManagerOpen = 0x%x %s\n", kr,
           kr == kIOReturnSuccess ? "OK" : "FAILED");
    fflush(stdout);
    if (kr != kIOReturnSuccess) return 1;

    printf("listening: VendorID 0x%04x, UsagePage 0x%02x only\n",
           RAZER_VENDOR_ID, CONSUMER_PAGE);
    fflush(stdout);
    CFRunLoopRun();
    return 0;
}
