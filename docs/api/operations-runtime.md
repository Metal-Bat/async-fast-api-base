# Operations runtime additions / افزوده‌های اجرای عملیات

This local contract extends the platform-runtime contract. Live FastAPI OpenAPI remains authoritative. These changes are tested locally and are not a deployment.

این قرارداد محلی مکمل قرارداد اجرای پلتفرم است. سند زنده OpenAPI مرجع نهایی است؛ این تغییرات فقط محلی آزمایش شده‌اند.

## Private content / محتوای خصوصی

Authorized request/work-item attachment content returns raw binary bytes (`application/octet-stream`); report downloads return a private ZIP. They have no success JSON envelope. Errors retain the documented public error envelope. Responses use `Cache-Control: private, no-store`, `Content-Disposition` and `X-Content-Type-Options: nosniff`. Ownership/participant checks are performed before storage access; unauthorized resources return 404. Generic media retains its existing MIME-specific contract.

محتوای پیوست مجاز به صورت باینری و گزارش به صورت ZIP خصوصی برگردانده می‌شود؛ خطاها پوشش JSON عمومی دارند. کنترل مالکیت یا مشارکت پیش از دسترسی به ذخیره‌سازی انجام می‌شود و منبع غیرمجاز پاسخ ۴۰۴ دارد.

## Resource history / تاریخچه منبع

`POST /api/v1/business-requests/{ref_id}/history` requires `requests.start` and request ownership or superuser authority. `POST /api/v1/work-items/{ref_id}/history` requires `requests.start` and the ordinary work-item visibility check. Both accept bounded `ResourceHistoryQuery` pages and return `PageResponse[Page[ResourceHistoryDTO]]`. Search/sort fields are restricted to `changed_at` and `operation`; response records contain only those fields and nullable `version`. Canonical values, users, comments, command details and arbitrary entity names are not exposed. Invalid query input returns 422; invalid/unauthorized references follow the existing 404 contract. No new idempotency or stale-write rule applies to these read operations.

تاریخچه درخواست فقط برای مالک یا مدیر ارشد و تاریخچه کار فقط برای بازیگر دارای دسترسی کار در دسترس است. جستجو محدود به زمان و نوع عملیات است؛ مقادیر فرم، کاربران و جزئیات دستور افشا نمی‌شوند. ورودی نامعتبر پاسخ ۴۲۲ و منبع نامعتبر یا غیرمجاز پاسخ ۴۰۴ دارد.

## Collections, pages and corrections / مجموعه، صفحات و اصلاحات

Request collection commands now return `SuccessResponse[RuntimeFormStateDTO]` with the current revision-bearing resource reference after commit. Existing command bodies, collection validation and stale reference checks remain authoritative. Actor-filtered page settings may include at most 32 declared pages, unique keys of at most 64 characters, titles of at most 256 characters and up to 256 readable scopes per page. Hidden or unknown scopes and empty pages are removed. Only declared navigation metadata is exposed; no authored script is executed. Presentation resume remains an explicit authorized command with the existing form-version pin semantics.

دستور مجموعه، وضعیت اجرا و شناسه نسخه جاری را پس از ثبت برمی‌گرداند. حداکثر ۳۲ صفحه با محدوده‌های مجاز قابل نمایش است. محدوده پنهان یا ناشناخته حذف می‌شود. ادامه ارائه همچنان دستور صریح و مجاز است.

Correction views include optional actor-filtered `before_item_identity` alongside `before_data`; clients resolve prior repeated values by stable identity, never by a reordered index. Task save/finish recompute derived values after the permission-aware merge. Omitted or unchanged prior calculated values may be recomputed; explicitly forged calculated values still return sanitized validation errors. Hidden values remain canonical on the server and cannot be supplied by unauthorized actors. Existing override provenance and stale override checks remain enforced.

نمای اصلاح، هویت پایدار ردیف‌های قبلی را همراه داده قبلی مجاز ارائه می‌کند. ذخیره و پایان کار محاسبات را پس از ادغام مجاز دوباره اجرا می‌کنند؛ مقدار محاسباتی جعل‌شده همچنان رد می‌شود. داده پنهان در سرور حفظ و برای بازیگر غیرمجاز غیرقابل ارسال است.

## Local evidence / شواهد محلی

Regression tests cover actual schemas, binary headers, page projection, revision-bearing collection responses and derived-value tampering. The HTTP journey uses ordinary accounts and PostgreSQL; the Firefox runner in the frontend uses the same backend and session boundary. The opt-in `RUN_REPORT_WORKER=1` integration test uses a real reporting worker and private object storage to verify READY, owned download, outsider rejection and deletion. `scripts/seed_frontend_browser.py` is test-environment-only and writes a mode-0600 credential fixture for disposable accounts; delete it after verification. It must never be used with production data.

آزمون‌های محلی قرارداد، فیلتر دسترسی، ذخیره و پایان را بررسی می‌کنند. آزمون اختیاری گزارش از worker و ذخیره‌سازی واقعی استفاده می‌کند. داده ورود آزمون فقط برای حساب‌های موقت است و باید پس از آزمایش حذف شود.
