# Mutation conflict categories

Request and work-item mutations preserve HTTP 409, application code 1004, request_id and the localized error envelope. An optional data.conflict_kind carries one safe category: revision for a stale opaque reference, lifecycle for a rejected state/pin prerequisite, idempotency for command-key ownership or payload mismatch, or unknown when classification is unavailable. Clients must treat missing categories as unknown, retain their edits, perform an authorized current-state read and never automatically replay a command. Categories contain no exception text, values, hidden fields or command payload hashes.

Example: {"success":false,"code":1004,"request_id":"fixture-request","error":"The resource was modified. Refresh and try again.","data":{"conflict_kind":"idempotency"}}. The actor still needs the endpoint's original authentication, role and current-resource authorization. This metadata does not grant access or make a non-idempotent row/attachment mutation replayable. Existing ErrorResponse.data already permits structured details; operation IDs, statuses and generated DTO shapes remain unchanged.

## فارسی

پاسخ تعارض همچنان HTTP 409، کد 1004، شناسه درخواست و پیام محلی دارد. فیلد اختیاری data.conflict_kind فقط یکی از دسته‌های revision (مرجع قدیمی)، lifecycle (وضعیت یا پیش‌نیاز نامعتبر)، idempotency (ناسازگاری مالک یا محتوای کلید فرمان) و unknown را برمی‌گرداند. نام دسته‌ها، کلیدها و مراجع ترجمه نمی‌شوند. کلاینت باید ویرایش‌ها را حفظ کند، وضعیت جاری مجاز را بخواند و فرمان را خودکار تکرار نکند. متن خطا، مقدار خصوصی و هش محتوای فرمان منتشر نمی‌شود. مجوزهای اصلی هر مسیر بدون تغییر اعمال می‌شوند.
