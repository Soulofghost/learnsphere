const API_BASE = window.location.origin.includes('localhost') || window.location.origin.includes('127.0.0.1')
  ? '' 
  : '';

let currentCourse = null;
let currentModule = null;
let activeQuizData = null;

// DOM Elements
const activeUserEmailInput = document.getElementById('activeUserEmail');
const courseGrid = document.getElementById('courseGrid');
const filterCategory = document.getElementById('filterCategory');

// Classroom Elements
const classCourseTitle = document.getElementById('classCourseTitle');
const classCourseDesc = document.getElementById('classCourseDesc');
const classProgressWrap = document.getElementById('classProgressWrap');
const classProgressPct = document.getElementById('classProgressPct');
const classProgressBar = document.getElementById('classProgressBar');
const syllabusModuleList = document.getElementById('syllabusModuleList');
const startQuizBtn = document.getElementById('startQuizBtn');

// Viewer Elements
const viewerModuleTitle = document.getElementById('viewerModuleTitle');
const viewerModuleDuration = document.getElementById('viewerModuleDuration');
const viewerModuleContent = document.getElementById('viewerModuleContent');
const viewerFooter = document.getElementById('viewerFooter');
const markModuleCompleteBtn = document.getElementById('markModuleCompleteBtn');

// Navigation Tabs
const tabBtns = document.querySelectorAll('.tab-btn');
const tabViews = document.querySelectorAll('.tab-view');

tabBtns.forEach(btn => {
  btn.addEventListener('click', () => {
    tabBtns.forEach(b => b.classList.remove('active'));
    tabViews.forEach(v => v.classList.remove('active'));

    btn.classList.add('active');
    const tab = btn.dataset.tab;

    if (tab === 'catalog') {
      document.getElementById('tabCatalog').classList.add('active');
      loadCourses();
    } else if (tab === 'classroom') {
      document.getElementById('tabClassroom').classList.add('active');
    } else if (tab === 'verify') {
      document.getElementById('tabVerify').classList.add('active');
    }
  });
});

// Load Course Catalog
async function loadCourses() {
  try {
    let url = `${API_BASE}/api/courses?`;
    if (filterCategory.value) url += `category=${encodeURIComponent(filterCategory.value)}`;

    const res = await fetch(url);
    const data = await res.json();
    renderCourses(data.courses);
  } catch (err) {
    courseGrid.innerHTML = `<p class="text-crimson">Failed to load courses</p>`;
  }
}

function renderCourses(courses) {
  if (!courses || courses.length === 0) {
    courseGrid.innerHTML = `<p class="text-muted">No courses found matching criteria.</p>`;
    return;
  }

  courseGrid.innerHTML = courses.map(c => `
    <div class="course-card">
      <div class="card-top">
        <span class="pill-discipline">${c.category}</span>
        <span class="pill-level">${c.level}</span>
      </div>
      <div>
        <h3 class="card-title">${escapeHtml(c.title)}</h3>
        <p class="card-desc" style="margin-top: 0.5rem;">${escapeHtml(c.description)}</p>
      </div>
      <div class="card-meta">
        <span>⏱ ${c.duration_hours} hrs</span>
        <span>📖 ${c.modules_count} Lessons</span>
        <span>👤 ${escapeHtml(c.instructor)}</span>
      </div>
      <div class="card-actions">
        <span class="instructor-text">Accredited Syllabus</span>
        <button class="btn btn-primary" onclick="enrollAndOpen('${c.id}')">Enroll & Learn →</button>
      </div>
    </div>
  `).join('');
}

// Enroll and Switch to Classroom
window.enrollAndOpen = async function(courseId) {
  const email = activeUserEmailInput.value.trim() || 'alex.engineer@tech.internal';
  const name = email.split('@')[0].replace('.', ' ').toUpperCase();

  try {
    await fetch(`${API_BASE}/api/courses/${courseId}/enroll`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_name: name, user_email: email })
    });

    await loadCourseClassroom(courseId);

    // Switch to classroom tab
    tabBtns.forEach(b => b.classList.remove('active'));
    tabViews.forEach(v => v.classList.remove('active'));
    document.querySelector('[data-tab="classroom"]').classList.add('active');
    document.getElementById('tabClassroom').classList.add('active');

  } catch (err) {
    alert('Failed to enroll in course');
  }
};

// Load Course in Classroom
async function loadCourseClassroom(courseId) {
  const email = activeUserEmailInput.value.trim() || 'alex.engineer@tech.internal';

  try {
    const res = await fetch(`${API_BASE}/api/courses/${courseId}?user_email=${encodeURIComponent(email)}`);
    if (!res.ok) return;
    const data = await res.json();
    currentCourse = data;

    classCourseTitle.textContent = data.title;
    classCourseDesc.textContent = `Instructor: ${data.instructor} | Level: ${data.level}`;
    classProgressWrap.style.display = 'block';

    const progress = data.enrollment ? data.enrollment.progress_pct : 0;
    classProgressPct.textContent = `${progress}%`;
    classProgressBar.style.width = `${progress}%`;

    const completedIds = data.enrollment ? data.enrollment.completed_modules : [];

    syllabusModuleList.innerHTML = data.modules.map((m, idx) => {
      const isCompleted = completedIds.includes(m.id);
      return `
        <div class="module-item" id="mod-item-${m.id}" onclick="selectModule('${m.id}')">
          <div style="display: flex; align-items: center; gap: 0.5rem;">
            <span class="module-check ${isCompleted ? 'completed' : ''}">${isCompleted ? '✓' : '○'}</span>
            <span class="module-item-title">${idx + 1}. ${escapeHtml(m.title)}</span>
          </div>
          <span style="font-size: 0.72rem; color: var(--text-muted);">${m.duration_minutes}m</span>
        </div>
      `;
    }).join('');

    // Toggle quiz button if syllabus 100% completed
    if (progress >= 100.0 && data.quiz) {
      startQuizBtn.style.display = 'block';
    } else {
      startQuizBtn.style.display = 'none';
    }

    if (data.modules.length > 0) {
      selectModule(data.modules[0].id);
    }

  } catch (err) {
    console.error(err);
  }
}

// Select Module
window.selectModule = function(moduleId) {
  if (!currentCourse) return;
  const mod = currentCourse.modules.find(m => m.id === moduleId);
  if (!mod) return;
  currentModule = mod;

  document.querySelectorAll('.module-item').forEach(el => el.classList.remove('active'));
  const activeEl = document.getElementById(`mod-item-${moduleId}`);
  if (activeEl) activeEl.classList.add('active');

  viewerModuleTitle.textContent = mod.title;
  viewerModuleDuration.textContent = `${mod.duration_minutes} mins estimated`;
  viewerModuleContent.innerHTML = `
    <div style="background: var(--bg-surface); border: 1px solid var(--border-color); border-radius: 8px; padding: 1.5rem; margin-bottom: 1rem;">
      <h4 style="color: var(--emerald); margin-bottom: 0.5rem;">Lesson Brief & Theoretical Foundation</h4>
      <p style="font-size: 0.95rem; line-height: 1.7;">${escapeHtml(mod.content)}</p>
    </div>
    <div style="background: rgba(99, 102, 241, 0.08); border: 1px solid rgba(99, 102, 241, 0.2); border-radius: 8px; padding: 1rem; font-size: 0.85rem; color: #a5b4fc;">
      💡 <strong>Engineering Note:</strong> Thoroughly study consensus, partitioning rules, and fault recovery before proceeding to the final certification assessment.
    </div>
  `;
  viewerFooter.style.display = 'flex';
};

// Mark Module Completed
markModuleCompleteBtn.addEventListener('click', async () => {
  if (!currentCourse || !currentModule) return;
  const email = activeUserEmailInput.value.trim() || 'alex.engineer@tech.internal';

  try {
    const res = await fetch(`${API_BASE}/api/courses/${currentCourse.id}/modules/${currentModule.id}/complete`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_email: email })
    });

    if (res.ok) {
      await loadCourseClassroom(currentCourse.id);
    }
  } catch (err) {
    alert('Failed to record lesson completion');
  }
});

// Quiz Assessment Modal
const quizModal = document.getElementById('quizModal');
const closeQuizModalBtn = document.getElementById('closeQuizModal');
const cancelQuizBtn = document.getElementById('cancelQuizBtn');
const quizForm = document.getElementById('quizForm');
const quizQuestionsContainer = document.getElementById('quizQuestionsContainer');

startQuizBtn.addEventListener('click', async () => {
  if (!currentCourse) return;

  try {
    const res = await fetch(`${API_BASE}/api/courses/${currentCourse.id}/quiz`);
    if (!res.ok) return;
    activeQuizData = await res.json();

    document.getElementById('quizModalTitle').textContent = activeQuizData.title;

    quizQuestionsContainer.innerHTML = activeQuizData.questions.map((q, qIdx) => `
      <div class="quiz-q-card">
        <div style="font-weight: 600; font-size: 0.9rem;">${qIdx + 1}. ${escapeHtml(q.question_text)}</div>
        <div class="quiz-options">
          ${q.options.map((opt, optIdx) => `
            <label class="quiz-option-label">
              <input type="radio" name="question_${q.id}" value="${optIdx}" required>
              <span>${escapeHtml(opt)}</span>
            </label>
          `).join('')}
        </div>
      </div>
    `).join('');

    quizModal.classList.add('open');
  } catch (err) {
    alert('Failed to load quiz');
  }
});

function closeQuiz() {
  quizModal.classList.remove('open');
}
closeQuizModalBtn.addEventListener('click', closeQuiz);
cancelQuizBtn.addEventListener('click', closeQuiz);

// Submit Quiz
quizForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  if (!activeQuizData || !currentCourse) return;

  const email = activeUserEmailInput.value.trim() || 'alex.engineer@tech.internal';
  const name = email.split('@')[0].replace('.', ' ').toUpperCase();

  const answers = {};
  activeQuizData.questions.forEach(q => {
    const selected = document.querySelector(`input[name="question_${q.id}"]:checked`);
    if (selected) {
      answers[q.id] = parseInt(selected.value, 10);
    }
  });

  try {
    const res = await fetch(`${API_BASE}/api/courses/${currentCourse.id}/quiz/submit`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        user_name: name,
        user_email: email,
        answers: answers
      })
    });

    const result = await res.json();
    closeQuiz();

    if (result.passed) {
      showCertificateAward(result, name);
    } else {
      alert(`Score: ${result.score_pct}%. You did not meet the 75% passing threshold. Please review the material and try again.`);
    }

  } catch (err) {
    alert('Assessment evaluation failed');
  }
});

// Certificate Award Modal
const awardModal = document.getElementById('awardModal');
const closeAwardModalBtn = document.getElementById('closeAwardModal');
const closeAwardBtn = document.getElementById('closeAwardBtn');
const certificateFrame = document.getElementById('certificateFrame');

function showCertificateAward(result, name) {
  const certCode = result.certificate ? result.certificate.cert_code : 'CERT-PENDING';

  certificateFrame.innerHTML = `
    <div class="cert-badge">🎖️</div>
    <div class="cert-title">Certificate of Mastery</div>
    <div style="font-size: 0.85rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.1em;">LearnSphere Global Engineering Accreditation</div>
    <div class="cert-name">${escapeHtml(name)}</div>
    <div class="cert-details">
      has successfully completed all required curriculum coursework and demonstrated mastery in<br>
      <strong style="color: #fff; font-size: 1.15rem;">${escapeHtml(currentCourse.title)}</strong><br>
      Achieving an assessment grade of <strong>${result.score_pct}%</strong>
    </div>
    <div style="font-size: 0.8rem; color: var(--text-subtle);">
      Verification Credential ID:<br>
      <span class="cert-code-tag">${certCode}</span>
    </div>
  `;

  awardModal.classList.add('open');
}

function closeAward() {
  awardModal.classList.remove('open');
}
closeAwardModalBtn.addEventListener('click', closeAward);
closeAwardBtn.addEventListener('click', closeAward);

// Certificate Verification Form
const verifyCertForm = document.getElementById('verifyCertForm');
const certCodeInput = document.getElementById('certCodeInput');
const certResultBox = document.getElementById('certResultBox');

verifyCertForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  const code = certCodeInput.value.trim();
  if (!code) return;

  try {
    const res = await fetch(`${API_BASE}/api/certificates/${encodeURIComponent(code)}/verify`);
    if (!res.ok) {
      certResultBox.style.display = 'block';
      certResultBox.innerHTML = `
        <div style="color: var(--crimson); font-weight: 700;">✗ INVALID CREDENTIAL</div>
        <p style="font-size: 0.85rem; color: var(--text-muted);">No cryptographic credential record matches ID: <strong>${escapeHtml(code)}</strong></p>
      `;
      return;
    }

    const cert = await res.json();
    certResultBox.style.display = 'block';
    certResultBox.innerHTML = `
      <div style="display: flex; justify-content: space-between; align-items: center;">
        <span style="color: var(--emerald); font-weight: 700; font-family: var(--font-mono);">✓ VERIFIED AUTHENTIC</span>
        <span style="font-family: var(--font-mono); font-size: 0.8rem; background: var(--emerald-bg); color: var(--emerald); padding: 2px 6px; border-radius: 4px;">${cert.cert_code}</span>
      </div>
      <div style="font-size: 1.1rem; font-weight: 700; color: #fff;">${escapeHtml(cert.recipient_name)}</div>
      <div style="font-size: 0.9rem; color: var(--text-muted);">
        Course: <strong>${escapeHtml(cert.course_title)}</strong><br>
        Instructor: ${escapeHtml(cert.instructor)} | Duration: ${cert.duration_hours}h<br>
        Assessment Score: <strong style="color: var(--emerald);">${cert.score_percentage}%</strong><br>
        Issued: ${new Date(cert.issued_at).toLocaleDateString()}
      </div>
    `;
  } catch (err) {
    alert('Verification service unreachable');
  }
});

function escapeHtml(str) {
  if (!str) return '';
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
}

filterCategory.addEventListener('change', loadCourses);

// Initialize
loadCourses();
