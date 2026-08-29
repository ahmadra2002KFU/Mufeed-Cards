# Mufeed Cards

بطاقات العمل الإلكترونية لفريق مفيد — تعمل عبر NFC وQR.
كل بطاقة على رابط: **`cards.mufeedai.com/<slug>`**، والصفحة الرئيسية أداة إضافة ذاتية: عبّئ النموذج وستحصل على ملف بطاقتك جاهزًا (إنشاء مباشر على GitHub، أو تنزيل، أو إرسال للمسؤول عبر واتساب).

## البنية

- `people/<slug>/card.json` + صورة `photo.jpg` اختيارية — بيانات كل شخص
- `tools/build.py` — يولد `site/` (صفحة لكل شخص + vCard بالصورة + الفهرس/الأداة)
- `.github/workflows/deploy.yml` — يبني وينشر تلقائيًا عند كل دفعة إلى main
- النطاق: `cards.mufeedai.com` (ملف CNAME يتولد تلقائيًا)

## تشغيل محلي

```
pip install pillow
python tools/build.py
python -m http.server 5603 --directory site
```
