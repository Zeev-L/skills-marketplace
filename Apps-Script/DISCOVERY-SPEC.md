# 🔮 אפיון: חילוץ אוטומטי של "משימות שנשכחו" (Task Discovery)

מסמך אפיון **נייד** להרחבת מנהל המשימות: סריקת מיילים (ובהמשך סלאק) שהגיעו מאז הסנכרון האחרון,
וחילוץ משימות פוטנציאליות שעוד לא נמצאות בטבלה — בעזרת מודל AI.

> **המסמך הזה הוא אפיון בלבד — לא קוד מיושם.** הוא נכתב כדי שאפשר יהיה לקחת אותו לכל מקום עבודה,
> עם כל מודל AI, ולממש לפיו. אין בו שום הנחה ספציפית לארגון כלשהו — כל מה שתלוי-מקום יושב ב-`CONFIG`.

---

## 🎯 המטרה
לפעמים משימות "נופלות בין הכיסאות": מישהו כתב לך במייל או בסלאק "תוכל להכין X?", ולא תייגת את זה.
הרעיון: **סוכן שסורק את התקשורת מאז הריצה האחרונה, מזהה בקשות/מטלות שמכוונות אליך, ומציע אותן כמשימות לאישור.**

עיקרון מנחה: **לא להכניס שום דבר אוטומטית לטבלת המשימות.** כל מה שה-AI מחלץ נכנס ללשונית "הצעות",
ורק מה שאתה מאשר עובר ל"משימות". זה מונע הצפה ברעש ושומר עליך בשליטה.

---

## 🧩 ארכיטקטורה — שכבות מנותקות

```
┌─────────────┐    ┌──────────────┐    ┌─────────────┐    ┌──────────────┐
│  מקורות     │ →  │  שכבת AI     │ →  │  דה-דופ     │ →  │  לשונית      │
│ Email/Slack │    │ (אדפטר נייד) │    │ מול הקיים   │    │ "הצעות"      │
└─────────────┘    └──────────────┘    └─────────────┘    └──────────────┘
       ↑                                                          ↓
  lastDiscoveryRun (PropertiesService)              אישור ידני → "משימות"
```

כל שכבה מנותקת מהאחרות, כך שאפשר להחליף מקור או מודל AI בלי לגעת בשאר.

---

## 1. חותמת זמן — "מאז הריצה האחרונה"
- לשמור `lastDiscoveryRun` (timestamp במילישניות) ב-`PropertiesService.getScriptProperties()`.
- בכל ריצה: לסרוק מקורות מאז החותמת, ובסוף ריצה מוצלחת — לעדכן את החותמת ל"עכשיו".
- ריצה ראשונה ללא חותמת: ברירת מחדל ל-X ימים אחורה (לפי `CONFIG.firstRunLookbackDays`).

```js
function getLastRun_() {
  const v = PropertiesService.getScriptProperties().getProperty('lastDiscoveryRun');
  return v ? Number(v) : (Date.now() - CONFIG.firstRunLookbackDays * 86400000);
}
function setLastRun_(ts) {
  PropertiesService.getScriptProperties().setProperty('lastDiscoveryRun', String(ts));
}
```

---

## 2. מקור מיילים (קל — מובנה ב-Apps Script)
- שאילתת Gmail למיילים שהגיעו מאז החותמת (Gmail תומך ב-`after:` בפורמט תאריך):
  ```js
  const query = 'in:inbox after:' + Utilities.formatDate(new Date(getLastRun_()),
                Session.getScriptTimeZone(), 'yyyy/MM/dd');
  const threads = GmailApp.search(query, 0, CONFIG.maxThreads);
  ```
- מכל הודעה נחלץ "בלוק טקסט" אחיד עבור ה-AI:
  `{ source: 'email', id: threadId, from, subject, snippet/body, date }`.
- **היקף התוכן ניתן-להגדרה** (`CONFIG.contentScope`): `'subject'` (נושאים בלבד),
  `'snippet'` (נושא + תקציר קצר), או `'body'` (גוף מלא). ראה הערת הפרטיות בסעיף 8.

---

## 3. מקור סלאק (אופציונלי — מודולרי)
> מודול נפרד ש**ניתן לכיבוי** ב-`CONFIG.sources.slack = false`. דורש יותר הקמה, ולכן מופרד לחלוטין.

- דורש **Slack App + Bot/User Token** (scopes לקריאה: `channels:history`, `groups:history`,
  `im:history`, `users:read`). **בחלק מהארגונים יצירת אפליקציית Slack דורשת אישור אדמין** —
  זו תלות חיצונית שצריך לוודא לפני מימוש.
- קריאה דרך `UrlFetchApp` ל-Slack Web API (`conversations.history` עם `oldest=<lastRun>`),
  על רשימת ערוצים/DMs מתוך `CONFIG.slack.channels`.
- אותו פורמט בלוק-טקסט אחיד כמו במיילים: `{ source: 'slack', id, from, channel, text, date }`.
- הטוקן נשמר **רק** ב-Script Properties (ראה סעיף 8) — לעולם לא בקוד.

המבנה האחיד של בלוקי הטקסט מאפשר לשכבת ה-AI להיות **אדישה למקור** — אותו קוד מטפל במייל ובסלאק.

---

## 4. שכבת AI אגנוסטית (תקע-והחלף)
ממשק יחיד שלא יודע מי הספק:

```js
// מקבל בלוקי טקסט + רשימת המשימות הקיימות, מחזיר מערך הצעות:
// [{ category, task, sourceType, sourceId, confidence, reason }]
function extractTasks(textBlobs, existingTasks) {
  return AI_ADAPTER.call(buildPrompt_(textBlobs, existingTasks));
}
```

- כל ספק ממומש כ**אדפטר** קטן עם פונקציה אחת `call(prompt) → text`. החלפת ספק =
  החלפת `AI_ADAPTER` בלבד (Gemini / Claude / OpenAI / מקומי). דוגמת אדפטר:
  ```js
  const GeminiAdapter = {
    call(prompt) {
      const res = UrlFetchApp.fetch(ENDPOINT + '?key=' + getSecret_('AI_API_KEY'), {
        method: 'post', contentType: 'application/json',
        payload: JSON.stringify({ contents: [{ parts: [{ text: prompt }] }] })
      });
      return JSON.parse(res.getContentText()); // לחלץ את הטקסט לפי מבנה התשובה של הספק
    }
  };
  ```
- **ספציפיקציית הפרומפט:**
  - תפקיד: "אתה עוזר שמזהה משימות שמכוונות אל המשתמש מתוך תקשורת."
  - קלט: בלוקי הטקסט + רשימת המשימות הקיימות (קטגוריה + שם).
  - הוראות: לזהות רק מטלות אמיתיות שדורשות פעולה **מהמשתמש**; להתעלם מ-FYI/ניוזלטרים/ספאם;
    **לא** להציע משהו שכבר מופיע ברשימת הקיימות; לנסח כל משימה במבנה `קטגוריה - משימה`
    (תואם לפורמט הקיים בסקריפט).
  - פלט: **JSON בלבד** — מערך אובייקטים `{category, task, sourceType, sourceId, confidence, reason}`.
- מומלץ לבקש מהמודל פלט מובנה (JSON mode / schema) כדי להימנע מפרסינג שביר.

---

## 5. דה-דופ מול הקיים
שתי שכבות הגנה מפני כפילויות:
1. **בתוך הפרומפט** — מעבירים את רשימת המשימות הקיימות ומבקשים לא להציע חזרות (סינון סמנטי ע"י המודל).
2. **בקוד** — לפני כתיבה ללשונית "הצעות": לדלג על הצעה ש-`category - task` שלה כבר קיים ב"משימות"
   או כבר קיים ב"הצעות" (התאמה מדויקת, כגיבוי לסינון של ה-AI).

---

## 6. לשונית "הצעות" + זרימת אישור
- לשונית בשם `CONFIG.suggestionsSheet` (למשל "הצעות") עם עמודות:
  `[✓ אשר] | קטגוריה | משימה | מקור | קישור למקור | ביטחון | סיבה`.
- עמודת "אשר" היא **checkbox** (`SpreadsheetApp.newDataValidation().requireCheckbox()`).
- פריט תפריט **"✅ העבר הצעות מאושרות"** (`promoteApprovedSuggestions`):
  - עובר על שורות מסומנות, מוסיף כל אחת ל"משימות" (באותו פורמט: `taskId, category, task, "OPEN", ...`),
    ומוחק/מסמן את השורה ב"הצעות".
  - לאחר מכן מריץ `applyColors` כדי לצבוע.
- פריט תפריט **"🔮 חפש משימות שנשכחו"** (`runDiscovery`) — מריץ את כל הזרימה וממלא את "הצעות".
- אופציונלי: טריגר יומי ל-`runDiscovery` (באותה תבנית `enable.../disable...` כמו בסקריפט הראשי).

---

## 7. בלוק CONFIG (כל מה שתלוי-מקום במקום אחד)
```js
const CONFIG = {
  tasksSheet: 'משימות',
  suggestionsSheet: 'הצעות',
  firstRunLookbackDays: 3,
  maxThreads: 50,
  contentScope: 'snippet',      // 'subject' | 'snippet' | 'body'
  aiProvider: 'gemini',         // 'gemini' | 'claude' | ...
  sources: { email: true, slack: false },
  slack: { channels: [] }       // למילוי רק אם מפעילים סלאק
};
```
החלפת מקום עבודה / ספק / היקף תוכן = שינוי ב-`CONFIG` בלבד.

---

## 8. אבטחה ופרטיות ⚠️ (לקרוא לפני מימוש)
- **סודות רק ב-Script Properties — לעולם לא בקוד ולא בגיט.** מפתח ה-AI וטוקן הסלאק נשמרים דרך
  `PropertiesService.getScriptProperties().setProperty(...)` (הגדרה חד-פעמית), ונקראים דרך עוזר:
  ```js
  function getSecret_(name) {
    const v = PropertiesService.getScriptProperties().getProperty(name);
    if (!v) throw new Error('חסר סוד: ' + name + ' — הגדר אותו ב-Script Properties.');
    return v;
  }
  ```
- **שליחת תוכן ל-LLM חיצוני היא החלטת ממשל-מידע.** חילוץ משימות מחייב לשלוח תוכן תקשורת
  למודל חיצוני. בחשבון/תוכן ארגוני זו עשויה להיות בעיית מדיניות — **חובה לוודא שזה מותר**
  במקום העבודה לפני הפעלה. הקטנת סיכון: להתחיל ב-`contentScope: 'subject'` (נושאים בלבד),
  ולשקול מודל פרטי/בענן הארגוני אם נדרש.
- **הרשאות.** סריקת מיילים וסלאק דורשת scopes רחבים — להפעיל רק את המקורות שבאמת צריך
  (`CONFIG.sources`).

---

## ✅ סדר מימוש מומלץ
1. תשתית: `CONFIG`, חותמת זמן, לשונית "הצעות" + checkbox, `promoteApprovedSuggestions`.
2. מקור מיילים + אדפטר AI אחד (למשל Gemini) → זרימה מלאה מקצה-לקצה על מיילים בלבד.
3. כיוונון פרומפט ודה-דופ עד שההצעות איכותיות.
4. רק אז (אם רלוונטי וההרשאות מאפשרות): מודול סלאק.
