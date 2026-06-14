/**
 * 🚀 Gmail Task Manager v3.1 (Stable & Button Compatible)
 * -------------------------------------------------------
 * אותה גרסה 3.0 חזקה, אבל עם שם הפונקציה הישן (V2)
 * כדי שהכפתור שלך ימשיך לעבוד בלי שגיאות.
 */

function onOpen() {
  const ui = SpreadsheetApp.getUi();
  ui.createMenu('ניהול משימות')
      .addItem('🔄 סנכרן מיילים (Refresh)', 'syncGmailToSheetsV2') // הותאם לשם הפונקציה
      .addSeparator()
      .addItem('🎨 כפה צביעה מחדש', 'applyColors')
      .addToUi();
}

// שמרתי על השם V2 כדי שהכפתור שלך יעבוד, אבל הלוגיקה היא של v3.0
function syncGmailToSheetsV2() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sheet = ss.getSheetByName("משימות");
  
  // הגדרת הכותרות הקבועות
  const headers = ["Task ID", "קטגוריה", "משימה", "סטטוס", "דחיפות", "תאריך יעד", "הערות", "Thread ID"];

  // 1. יצירת גיליון אם לא קיים
  if (!sheet) {
    sheet = ss.insertSheet("משימות");
  }

  // --- שלב א': תחזוקת גיליון (כותרות ועיצוב) ---
  sheet.getRange(1, 1, 1, headers.length)
       .setValues([headers])
       .setFontWeight("bold")
       .setBackground("#e0e0e0")
       .setBorder(true, true, true, true, true, true);
       
  sheet.setFrozenRows(1);
  
  // הסתרת עמודות טכניות
  sheet.hideColumns(1); // Task ID
  sheet.hideColumns(8); // Thread ID

  // הגדרת Dropdown לעמודת הסטטוס (D)
  const maxRows = Math.max(sheet.getMaxRows(), 100);
  const rule = SpreadsheetApp.newDataValidation()
    .requireValueInList(['OPEN', 'IN PROGRESS', 'DEPENDENT', 'DONE'], true)
    .build();
  sheet.getRange(2, 4, maxRows - 1, 1).setDataValidation(rule);


  // --- שלב ב': קריאת המצב הקיים (Stateful) ---
  let existingMap = new Map();
  const lastRow = sheet.getLastRow();

  if (lastRow > 1) {
    const existingData = sheet.getRange(2, 1, lastRow - 1, 8).getValues();
    existingData.forEach((row, index) => {
      const taskId = String(row[0]); 
      existingMap.set(taskId, {
        rowIndex: index + 2,
        status: row[3], // עמודה D
        threadId: row[7] // עמודה H
      });
    });
  }

  // --- שלב ג': שליפת מיילים מ-Gmail ---
  const threads = GmailApp.search('label:MyTasks -in:trash');
  const activeThreadIds = new Set(); 
  const newRows = [];

  console.log(`נמצאו ${threads.length} מיילים בתגית MyTasks`);

  threads.forEach(thread => {
    const threadId = thread.getId();
    activeThreadIds.add(threadId);
    
    const message = thread.getMessages()[0];
    let subject = message.getSubject();
    
    // ניקוי תחיליות
    subject = subject.replace(/^(Re|Fwd|RE|FWD|הועבר|תשובה|Re: Re):\s*/gi, "").trim();
    
    // בדיקת מבנה: "נושא - משימה"
    const parts = subject.split(" - ");
    if (parts.length < 2) return;
    
    let category = parts[0].trim();
    const taskName = parts.slice(1).join(" - ").trim();
    
    // בדיקת עברית (חובה)
    const fullText = category + taskName;
    if (!/[\u0590-\u05FF]/.test(fullText)) return;
    
    // סינוני זבל
    if (category.includes(":") || category.toLowerCase().includes("invitation")) return;
    if (category.length > 25 || category.length < 2) return;
    
    const taskId = `${category} - ${taskName}`;

    // מניעת כפילויות
    if (existingMap.has(taskId)) return;

    // הוספה למאגר
    newRows.push([
      taskId, category, taskName, "OPEN", "", "", "", threadId
    ]);
  });

  // --- שלב ד': כתיבת משימות חדשות ---
  if (newRows.length > 0) {
    sheet.insertRowsBefore(2, newRows.length);
    sheet.getRange(2, 1, newRows.length, 8).setValues(newRows);
  }

  // --- שלב ה': סנכרון דו-כיווני ---
  const fullDataRange = sheet.getDataRange();
  if (fullDataRange.getLastRow() < 2) {
    return;
  }
  
  const currentData = sheet.getRange(2, 1, fullDataRange.getLastRow() - 1, 8).getValues();

  for (let i = 0; i < currentData.length; i++) {
    const row = currentData[i];
    const rowIndex = i + 2;
    const status = row[3]; // עמודה D
    const tId = row[7];    // עמודה H

    // 1. שיטס -> מייל (מחיקה לאשפה אם DONE)
    if (status === 'DONE' && tId) {
      try {
        const threadToArchive = GmailApp.getThreadById(tId);
        if (threadToArchive && !threadToArchive.isInTrash()) {
          threadToArchive.moveToTrash();
        }
      } catch (e) {}
    }

    // 2. מייל -> שיטס (סימון DONE אם המייל נעלם מ-MyTasks)
    if (status !== 'DONE' && tId && !activeThreadIds.has(tId)) {
      sheet.getRange(rowIndex, 4).setValue('DONE');
    }
  }

  // --- שלב ו': החלת צבעים ---
  applyColors(sheet, ss);
}

/**
 * פונקציית העיצוב הראשית
 */
function applyColors(sheet, ss) {
  const lastRow = sheet.getLastRow();
  if (lastRow < 2) return;

  let colorSheet = ss.getSheetByName("צבעים");
  if (!colorSheet) {
    colorSheet = ss.insertSheet("צבעים");
    colorSheet.appendRow(["קטגוריה", "צבע"]);
  }

  const colorData = colorSheet.getDataRange().getValues();
  const dynamicCategoryColors = {};
  for (let i = 1; i < colorData.length; i++) {
    if (colorData[i][0]) dynamicCategoryColors[colorData[i][0]] = colorData[i][1];
  }

  const colorsToUse = [
    "#f28b82", "#fbbc04", "#fff475", "#ccff90", "#a7ffeb",
    "#cbf0f8", "#aecbfa", "#d7aefb", "#fdcfe8", "#e6c9a8"
  ];

  const range = sheet.getRange(2, 1, lastRow - 1, 8);
  const values = range.getValues();
  
  const backgrounds = [];
  const fontColors = [];

  values.forEach(row => {
    const category = row[1];
    const status = String(row[3]).toUpperCase();
    
    // צבע בסיס
    let rowBaseColor = "#ffffff"; 
    if (category) {
      if (!dynamicCategoryColors[category]) {
        const usedColors = Object.values(dynamicCategoryColors);
        let nextColor = colorsToUse.find(c => !usedColors.includes(c));
        if (!nextColor) nextColor = "#e0e0e0";
        dynamicCategoryColors[category] = nextColor;
        colorSheet.appendRow([category, nextColor]);
      }
      rowBaseColor = dynamicCategoryColors[category];
    }
    
    let finalRowColor = (status === 'DONE') ? "#f3f3f3" : rowBaseColor;

    let rowBg = new Array(8).fill(finalRowColor);
    let rowFc = new Array(8).fill("black");

    // צבעי סטטוס
    switch (status) {
      case 'OPEN':
        rowBg[3] = "#cfe2f3"; // כחול בהיר
        rowFc[3] = "black";
        break;
      case 'IN PROGRESS':
        rowBg[3] = "#1155cc"; // כחול כהה
        rowFc[3] = "white";   // לבן
        break;
      case 'DEPENDENT':
        rowBg[3] = "#595959"; // אפור כהה
        rowFc[3] = "white";   // לבן
        break;
      case 'DONE':
        rowBg[3] = "#d9ead3"; // ירוק בהיר
        rowFc[3] = "black";
        break;
    }

    backgrounds.push(rowBg);
    fontColors.push(rowFc);
  });

  range.setBackgrounds(backgrounds);
  range.setFontColors(fontColors);
}
