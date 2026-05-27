from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import BrowserContext, Page, sync_playwright

from .profile import ApplicantProfile
from .status import (
    APPLY_CAPTCHA_DETECTED,
    APPLY_FAILED,
    APPLY_FILLED,
    APPLY_NEEDS_LOGIN,
    APPLY_NEEDS_MANUAL_INPUT,
    APPLY_SUBMITTED,
)


@dataclass
class ApplyExecutionResult:
    status: str
    msg: str
    screenshot_path: str | None = None

    @property
    def message(self) -> str:
        return self.msg


@dataclass
class LoginExecutionResult:
    status: str
    msg: str

    @property
    def message(self) -> str:
        return self.msg


def _launch_persistent_context(playwright, user_data_dir: Path, headless: bool) -> BrowserContext:
    common = dict(
        user_data_dir=str(user_data_dir),
        headless=headless,
        viewport={"width": 1400, "height": 900},
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-default-browser-check",
            "--disable-dev-shm-usage",
        ],
    )
    try:
        return playwright.chromium.launch_persistent_context(channel="chrome", **common)
    except Exception:
        return playwright.chromium.launch_persistent_context(**common)


def _try_fill(page: Page, selectors: list[str], value: str | None) -> bool:
    if not value:
        return False
    for selector in selectors:
        try:
            field = page.locator(selector).first
            field.wait_for(state="visible", timeout=1200)
            field.fill(value)
            return True
        except Exception:
            continue
    return False


def _try_select(page: Page, selectors: list[str], value: str | None) -> bool:
    if not value:
        return False
    for selector in selectors:
        try:
            field = page.locator(selector).first
            field.wait_for(state="visible", timeout=1200)
            field.select_option(label=value)
            return True
        except Exception:
            continue
    return False


def _try_fill_by_label(page: Page, labels: list[str], value: str | None) -> bool:
    if not value:
        return False
    for label in labels:
        try:
            field = page.get_by_label(label, exact=False).first
            field.wait_for(state="visible", timeout=1200)
            field.fill(value)
            return True
        except Exception:
            continue
    return False


def _is_login_page(page: Page) -> bool:
    url = page.url.lower()
    return (
        "login" in url
        or "signin" in url
        or "auth" in url
        or "candidate/login" in url
    )


def _click_apply(page: Page) -> bool:
    _dismiss_overlays(page)
    selectors = [
        "[data-automation='job-apply-button']",
        "[data-automation='apply-button']",
        "[data-automation='job-detail-apply']",
        "button:has-text('Apply')",
        "button:has-text('Apply now')",
        "button:has-text('Quick apply')",
        "a:has-text('Apply')",
        "a:has-text('Apply now')",
        "button:has-text('Lamar')",
        "button:has-text('Lamar sekarang')",
        "a:has-text('Lamar')",
        "a:has-text('Lamar sekarang')",
    ]
    for selector in selectors:
        try:
            btn = page.locator(selector).first
            btn.wait_for(state="visible", timeout=3000)
            btn.click()
            page.wait_for_load_state("domcontentloaded", timeout=5000)
            return True
        except Exception:
            continue
    return False


def _dismiss_overlays(page: Page) -> None:
    selectors = [
        "button:has-text('Accept all')",
        "button:has-text('Accept')",
        "button:has-text('Setuju')",
        "button:has-text('Saya setuju')",
        "button[aria-label='Close']",
        "button:has-text('Tutup')",
        "button:has-text('Close')",
    ]
    for selector in selectors:
        try:
            btn = page.locator(selector).first
            if btn.is_visible(timeout=400):
                btn.click(timeout=800)
        except Exception:
            continue


def _safe_wait_for_networkidle(page: Page, timeout_ms: int = 8000) -> None:
    try:
        page.wait_for_load_state("networkidle", timeout=timeout_ms)
    except Exception:
        # Many modern pages keep long-running network calls; do not fail apply flow on this.
        pass


def _detect_manual_reason(page: Page) -> str:
    content = page.content().lower()
    if "already applied" in content or "sudah melamar" in content:
        return "Already applied on this job."
    if "application closed" in content or "lowongan ditutup" in content:
        return "Job is closed or no longer accepting applications."
    if "external" in content and "apply" in content:
        return "This job likely redirects to external apply flow."
    return "Apply button not detected automatically."


def _has_submission_confirmation(page: Page) -> bool:
    content = page.content().lower()
    confirmation_terms = [
        "application submitted",
        "application sent",
        "applied successfully",
        "you've applied",
        "you have applied",
        "lamaran terkirim",
        "lamaran berhasil",
        "sudah melamar",
    ]
    return any(term in content for term in confirmation_terms)


def _click_final_submit(page: Page) -> bool:
    selectors = [
        "button:has-text('Submit application')",
        "button:has-text('Submit Application')",
        "button:has-text('Submit')",
        "button:has-text('Kirim lamaran')",
        "button:has-text('Kirim')",
        "[data-automation='submit-application']",
    ]
    for selector in selectors:
        try:
            btn = page.locator(selector).first
            btn.wait_for(state="visible", timeout=2000)
            btn.click()
            _safe_wait_for_networkidle(page, timeout_ms=10000)
            try:
                page.wait_for_function(
                    """
                    () => {
                      const text = document.body.innerText.toLowerCase();
                      return [
                        "application submitted",
                        "application sent",
                        "applied successfully",
                        "you've applied",
                        "you have applied",
                        "lamaran terkirim",
                        "lamaran berhasil",
                        "sudah melamar"
                      ].some((term) => text.includes(term));
                    }
                    """,
                    timeout=15000,
                )
            except Exception:
                pass
            return _has_submission_confirmation(page)
        except Exception:
            continue
    return False


def _click_continue_steps(page: Page) -> None:
    selectors = [
        "button:has-text('Continue')",
        "button:has-text('Lanjutkan')",
        "button:has-text('Next')",
        "button:has-text('Berikutnya')",
    ]
    final_selectors = [
        "button:has-text('Submit application')",
        "button:has-text('Submit Application')",
        "button:has-text('Kirim lamaran')",
        "[data-automation='submit-application']",
    ]
    for _ in range(8):
        for final_selector in final_selectors:
            try:
                if page.locator(final_selector).first.is_visible(timeout=700):
                    return
            except Exception:
                continue

        clicked = False
        for selector in selectors:
            try:
                btn = page.locator(selector).first
                btn.wait_for(state="visible", timeout=8000)
                btn.scroll_into_view_if_needed(timeout=3000)
                btn.click()
                page.wait_for_load_state("domcontentloaded", timeout=8000)
                _safe_wait_for_networkidle(page, timeout_ms=5000)
                clicked = True
                break
            except Exception:
                continue
        if not clicked:
            return


def run_jobstreet_apply(
    job_url: str,
    profile: ApplicantProfile,
    cv_path: Path,
    browser_profile_dir: Path,
    screenshots_dir: Path,
    headless: bool,
    timeout_sec: int,
    auto_submit: bool = False,
) -> ApplyExecutionResult:
    browser_profile_dir.mkdir(parents=True, exist_ok=True)
    screenshots_dir.mkdir(parents=True, exist_ok=True)
    screenshot_path = screenshots_dir / "last-apply.png"

    try:
        with sync_playwright() as playwright:
            ctx = _launch_persistent_context(playwright, browser_profile_dir, headless)
            try:
                page = ctx.new_page()
                page.set_default_timeout(timeout_sec * 1000)
                login_url = "https://id.jobstreet.com/login"
                page.goto(login_url, wait_until="domcontentloaded")
                _safe_wait_for_networkidle(page)

                if _is_login_page(page):
                    if not headless:
                        # Show login page first and wait until user is authenticated.
                        try:
                            page.wait_for_url(
                                lambda url: "login" not in url.lower()
                                and "signin" not in url.lower(),
                                timeout=timeout_sec * 1000,
                            )
                        except Exception:
                            page.screenshot(path=str(screenshot_path), full_page=True)
                            return ApplyExecutionResult(
                                status=APPLY_NEEDS_LOGIN,
                                msg="Login required. Please login in browser and retry.",
                                screenshot_path=str(screenshot_path),
                            )
                    else:
                        page.screenshot(path=str(screenshot_path), full_page=True)
                        return ApplyExecutionResult(
                            status=APPLY_NEEDS_LOGIN,
                            msg="Login required. Set apply_headless=false, login once, then retry.",
                            screenshot_path=str(screenshot_path),
                        )

                page.goto(job_url, wait_until="domcontentloaded")
                _safe_wait_for_networkidle(page)

                if "captcha" in page.content().lower():
                    page.screenshot(path=str(screenshot_path), full_page=True)
                    return ApplyExecutionResult(
                        status=APPLY_CAPTCHA_DETECTED,
                        msg="Captcha detected. Complete it manually and retry.",
                        screenshot_path=str(screenshot_path),
                    )

                if _is_login_page(page):
                    page.screenshot(path=str(screenshot_path), full_page=True)
                    return ApplyExecutionResult(
                        status=APPLY_NEEDS_LOGIN,
                        msg="Still on login page after redirect. Please complete login and retry.",
                        screenshot_path=str(screenshot_path),
                    )

                if not _click_apply(page):
                    page.screenshot(path=str(screenshot_path), full_page=True)
                    return ApplyExecutionResult(
                        status=APPLY_NEEDS_MANUAL_INPUT,
                        msg=_detect_manual_reason(page),
                        screenshot_path=str(screenshot_path),
                    )

                try:
                    file_input = page.locator("input[type='file']").first
                    file_input.wait_for(state="attached", timeout=2500)
                    file_input.set_input_files(str(cv_path))
                except Exception:
                    pass

                _try_fill(
                    page,
                    ["input[name*='name' i]", "input[placeholder*='name' i]"],
                    profile.full_name,
                )
                _try_fill_by_label(page, ["Name", "Nama"], profile.full_name)
                _try_fill(
                    page,
                    ["input[type='email']", "input[name*='email' i]"],
                    profile.email,
                )
                _try_fill_by_label(page, ["Email"], profile.email)
                _try_fill(
                    page,
                    ["input[type='tel']", "input[name*='phone' i]", "input[name*='mobile' i]"],
                    profile.phone,
                )
                _try_fill_by_label(page, ["Phone", "Mobile", "No. HP", "Nomor HP"], profile.phone)
                _try_fill(
                    page,
                    ["input[name*='location' i]", "textarea[name*='location' i]"],
                    profile.current_location,
                )
                _try_fill_by_label(page, ["Location", "Lokasi"], profile.current_location)
                _try_fill(
                    page,
                    ["input[name*='salary' i]", "input[placeholder*='salary' i]"],
                    profile.expected_salary,
                )
                _try_fill_by_label(
                    page,
                    ["Salary", "Gaji", "Expected salary", "Ekspektasi gaji"],
                    profile.expected_salary,
                )
                _try_select(
                    page,
                    ["select[name*='notice' i]", "select[id*='notice' i]"],
                    profile.notice_period,
                )
                _try_fill_by_label(
                    page,
                    ["Notice period", "Masa notice", "Ketersediaan bergabung"],
                    profile.notice_period,
                )
                _try_fill(
                    page,
                    [
                        "input[name*='linkedin' i]",
                        "input[placeholder*='linkedin' i]",
                        "input[name*='portfolio' i]",
                        "input[placeholder*='portfolio' i]",
                        "input[name*='github' i]",
                        "input[placeholder*='github' i]",
                        "input[name*='website' i]",
                        "input[placeholder*='website' i]",
                    ],
                    profile.portfolio_url or profile.linkedin_url or profile.github_url,
                )
                _try_fill_by_label(
                    page,
                    ["LinkedIn", "Portfolio", "Github", "GitHub", "Website"],
                    profile.portfolio_url or profile.linkedin_url or profile.github_url,
                )

                for key, answer in profile.default_answers.items():
                    _try_fill(
                        page,
                        [f"textarea[name*='{key}' i]", f"input[name*='{key}' i]"],
                        answer,
                    )

                _click_continue_steps(page)

                if auto_submit:
                    if _click_final_submit(page):
                        return ApplyExecutionResult(
                            status=APPLY_SUBMITTED,
                            msg="Application submitted automatically and confirmation was detected.",
                        )
                    page.screenshot(path=str(screenshot_path), full_page=True)
                    return ApplyExecutionResult(
                        status=APPLY_NEEDS_MANUAL_INPUT,
                        msg="Final submit button was not confirmed. Review the captured page manually.",
                        screenshot_path=str(screenshot_path),
                    )

                return ApplyExecutionResult(
                    status=APPLY_FILLED,
                    msg="Form auto-filled. Review the form manually before final submit.",
                )
            finally:
                ctx.close()
    except PlaywrightTimeoutError:
        return ApplyExecutionResult(
            status=APPLY_FAILED,
            msg="Timed out while opening or filling apply page.",
        )
    except Exception as exc:
        return ApplyExecutionResult(
            status=APPLY_FAILED,
            msg=f"Automation failed: {exc}",
        )


def run_jobstreet_login(
    browser_profile_dir: Path,
    headless: bool,
    timeout_sec: int,
) -> LoginExecutionResult:
    if headless:
        return LoginExecutionResult(
            status=APPLY_NEEDS_LOGIN,
            msg="Login flow requires browser UI. Set apply_headless=false.",
        )

    browser_profile_dir.mkdir(parents=True, exist_ok=True)

    try:
        with sync_playwright() as playwright:
            ctx = _launch_persistent_context(playwright, browser_profile_dir, False)
            try:
                page = ctx.new_page()
                page.set_default_timeout(timeout_sec * 1000)
                page.goto("https://id.jobstreet.com/login", wait_until="domcontentloaded")
                page.wait_for_url(
                    lambda url: "login" not in url.lower() and "signin" not in url.lower(),
                    timeout=timeout_sec * 1000,
                )
                return LoginExecutionResult(
                    status=APPLY_FILLED,
                    msg="Login detected and session saved in browser profile.",
                )
            except PlaywrightTimeoutError:
                return LoginExecutionResult(
                    status=APPLY_NEEDS_LOGIN,
                    msg="Login timeout. Retry and complete Google login in the opened browser.",
                )
            finally:
                ctx.close()
    except Exception as exc:
        return LoginExecutionResult(
            status=APPLY_FAILED,
            msg=f"Login automation failed: {exc}",
        )
