const state = {
  manifest: null,
  currentCourse: null,
  currentLocation: null,
  courseHistory: [],
  restoringLocation: false,
  collapsed: false,
  dashboardQuery: "",
};

const els = {
  pageTitle: document.querySelector("#pageTitle"),
  pageSubtitle: document.querySelector("#pageSubtitle"),
  mainArea: document.querySelector(".main-area"),
  dashboardView: document.querySelector("#dashboardView"),
  coursesView: document.querySelector("#coursesView"),
  globalToolView: document.querySelector("#globalToolView"),
  courseView: document.querySelector("#courseView"),
  emptyView: document.querySelector("#emptyView"),
  courseGrid: document.querySelector("#courseGrid"),
  dashboardSearch: document.querySelector("#dashboardSearch"),
  dashboardCourseCount: document.querySelector("#dashboardCourseCount"),
  dashboardCurrentCount: document.querySelector("#dashboardCurrentCount"),
  dashboardPastCount: document.querySelector("#dashboardPastCount"),
  archiveGenerated: document.querySelector("#archiveGenerated"),
  utFooter: document.querySelector(".ut-footer"),
  currentCoursesTable: document.querySelector("#currentCoursesTable"),
  pastCoursesTable: document.querySelector("#pastCoursesTable"),
  backButton: document.querySelector("#backButton"),
  downloadCourseTop: document.querySelector("#downloadCourseTop"),
  courseTerm: document.querySelector("#courseTerm"),
  courseTabs: document.querySelector("#courseTabs"),
  externalLinks: document.querySelector("#externalLinks"),
  panelModules: document.querySelector("#panelModules"),
  panelAnnouncements: document.querySelector("#panelAnnouncements"),
  panelFiles: document.querySelector("#panelFiles"),
  panelPages: document.querySelector("#panelPages"),
  panelAssignments: document.querySelector("#panelAssignments"),
  panelGrades: document.querySelector("#panelGrades"),
  panelQuizzes: document.querySelector("#panelQuizzes"),
  panelDiscussions: document.querySelector("#panelDiscussions"),
  panelPageDetail: document.querySelector("#panelPageDetail"),
  courseActions: document.querySelector("#courseActions"),
  viewerTitle: document.querySelector("#viewerTitle"),
  viewerHead: document.querySelector("#viewerHead"),
  viewerOpen: document.querySelector("#viewerOpen"),
  viewerBody: document.querySelector("#viewerBody"),
  collapseButton: document.querySelector("#collapseButton"),
  openOriginalButton: document.querySelector("#openOriginalButton"),
  fileOverlay: document.querySelector("#fileOverlay"),
  fileOverlayTitle: document.querySelector("#fileOverlayTitle"),
  fileOverlayFrame: document.querySelector("#fileOverlayFrame"),
  fileOverlayDownload: document.querySelector("#fileOverlayDownload"),
  fileOverlayClose: document.querySelector("#fileOverlayClose"),
};

async function loadManifest() {
  try {
    const response = await fetch("/api/manifest");
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    state.manifest = await response.json();
    renderDashboard();
  } catch {
    showEmpty();
  }
}

function showEmpty() {
  setGlobalActive("");
  resetCourseNavigation();
  els.mainArea.classList.remove("course-open");
  els.dashboardView.hidden = true;
  els.coursesView.hidden = true;
  els.globalToolView.hidden = true;
  els.courseView.hidden = true;
  els.emptyView.hidden = false;
  if (els.utFooter) els.utFooter.hidden = true;
  els.emptyView.innerHTML = `
    <h2>No archive found</h2>
    <p>Run the sync script first, then refresh this page.</p>
  `;
  els.backButton.hidden = true;
  setTopDownloadVisible(false);
  els.pageTitle.textContent = "Course Archive";
  els.pageSubtitle.textContent = "";
}

function renderDashboard() {
  setGlobalActive("dashboard");
  resetCourseNavigation();
  els.mainArea.classList.remove("course-open");
  els.emptyView.hidden = true;
  els.globalToolView.hidden = true;
  els.courseView.hidden = true;
  els.coursesView.hidden = true;
  els.dashboardView.hidden = false;
  if (els.utFooter) els.utFooter.hidden = false;
  els.backButton.hidden = true;
  setTopDownloadVisible(false);
  els.pageTitle.textContent = "Dashboard";
  els.pageSubtitle.textContent = "";
  els.courseGrid.innerHTML = "";
  if (els.dashboardSearch && els.dashboardSearch.value !== state.dashboardQuery) {
    els.dashboardSearch.value = state.dashboardQuery;
  }

  const allCourses = state.manifest.courses || [];
  const courses = dashboardCourses(allCourses);
  if (els.dashboardCourseCount) els.dashboardCourseCount.textContent = String(courses.length);
  if (els.dashboardCurrentCount) els.dashboardCurrentCount.textContent = String(allCourses.filter(isCurrentCourse).length);
  if (els.dashboardPastCount) els.dashboardPastCount.textContent = String(allCourses.filter(course => !isCurrentCourse(course)).length);
  if (els.archiveGenerated) els.archiveGenerated.textContent = "";

  if (!courses.length) {
    els.courseGrid.innerHTML = `
      <div class="dashboard-empty-card">
        <h2>No courses match this search</h2>
        <p>Clear the search field or run the sync script again if a course is missing from the archive.</p>
      </div>
    `;
    return;
  }

  for (const course of courses) {
    const card = document.createElement("button");
    card.className = "course-card";
    card.dataset.courseId = course.id;
    card.innerHTML = `
      <div class="course-color"></div>
      <div class="course-card-body">
        <div class="course-card-title">
          <h2>${escapeHtml(displayCourseName(course))}</h2>
        </div>
        <p class="course-code">${escapeHtml(course.course_code || displayCourseName(course))}</p>
        <p>${escapeHtml(course.term || course.state || "")}</p>
        <div class="course-card-actions" aria-hidden="true">
          <span class="card-action icon-assignment"></span>
          <span class="card-action icon-announcement"></span>
          <span class="card-action icon-discussion"></span>
        </div>
      </div>
    `;
    card.addEventListener("click", () => openCourse(course.id));
    els.courseGrid.appendChild(card);
  }
}

function dashboardCourses(courses) {
  const filtered = [...filteredDashboardCourses(courses)].sort(compareDashboardCourse);
  if (state.dashboardQuery) return filtered;
  const current = filtered.filter(isCurrentCourse);
  return current.length ? current : filtered;
}

function compareDashboardCourse(a, b) {
  const termCompare = String(b.term || "").localeCompare(String(a.term || ""), undefined, { numeric: true });
  if (termCompare) return termCompare;
  return displayCourseName(a).localeCompare(displayCourseName(b), undefined, { numeric: true });
}

function filteredDashboardCourses(courses) {
  const query = normalizeText(state.dashboardQuery);
  if (!query) return courses;
  return courses.filter(course => normalizeText([
    course.name,
    course.course_code,
    course.term,
    course.state,
    course.default_view,
  ].filter(Boolean).join(" ")).includes(query));
}

function labelForHomeView(view) {
  return {
    wiki: "Home page",
    modules: "Modules",
    assignments: "Assignments",
    syllabus: "Syllabus",
  }[view] || "Home";
}

function renderCoursesPage() {
  setGlobalActive("courses");
  resetCourseNavigation();
  els.mainArea.classList.remove("course-open");
  els.emptyView.hidden = true;
  els.dashboardView.hidden = true;
  els.globalToolView.hidden = true;
  els.courseView.hidden = true;
  els.coursesView.hidden = false;
  if (els.utFooter) els.utFooter.hidden = true;
  els.backButton.hidden = true;
  setTopDownloadVisible(false);
  els.pageTitle.textContent = "All Courses";
  els.pageSubtitle.textContent = "";

  const courses = state.manifest.courses || [];
  renderCourseTable(els.currentCoursesTable, courses.filter(isCurrentCourse), true);
  renderCourseTable(els.pastCoursesTable, courses.filter(course => !isCurrentCourse(course)), false);
}

function renderCourseTable(container, courses, includeUnpublished) {
  container.innerHTML = "";
  const header = document.createElement("div");
  header.className = "course-table-header";
  header.innerHTML = `
    <div>Favorite <span class="sort">▲</span></div>
    <div>Course <span class="sort">▲</span></div>
    <div>Nickname <span class="sort">▲</span></div>
    <div>Term <span class="sort">▲</span></div>
    <div>Enrolled as <span class="sort">▲</span></div>
    <div>Published <span class="sort">▲</span></div>
  `;
  container.appendChild(header);

  if (!courses.length) {
    const empty = document.createElement("div");
    empty.className = "course-table-row";
    empty.innerHTML = `<div></div><div>No courses in this section</div><div></div><div></div><div></div><div></div>`;
    container.appendChild(empty);
    return;
  }

  for (const course of courses) {
    const row = document.createElement("div");
    row.className = `course-table-row${course.name === String(course.id) ? " muted" : ""}`;
    row.innerHTML = `
      <div class="favorite">☆</div>
      <div>
        <span class="course-dot" style="background:${courseColor(course)}"></span>
        <button type="button" data-course-id="${escapeHtml(course.id)}">${escapeHtml(displayCourseName(course))}</button>
        ${course.nickname ? `<div class="nickname">${escapeHtml(course.nickname)}</div>` : ""}
      </div>
      <div></div>
      <div>${escapeHtml(course.term || "")}</div>
      <div>Student</div>
      <div>${includeUnpublished && course.name === String(course.id) ? "No" : "Yes"}</div>
    `;
    row.querySelector("button").addEventListener("click", () => openCourse(course.id));
    container.appendChild(row);
  }
}

function archiveSubtitle() {
  if (!state.manifest?.generated_at) return "";
  return `Generated ${new Date(state.manifest.generated_at).toLocaleString()}`;
}

async function openCourse(courseId) {
  setGlobalActive("courses");
  const response = await fetch(`/api/course/${courseId}`);
  const catalogCourse = (state.manifest.courses || []).find(course => String(course.id) === String(courseId));
  state.currentCourse = response.ok
    ? await response.json()
    : placeholderCourse(catalogCourse || { id: courseId, name: `Course ${courseId}` });
  state.currentLocation = null;
  state.courseHistory = [];
  state.restoringLocation = false;

  els.dashboardView.hidden = true;
  els.coursesView.hidden = true;
  els.globalToolView.hidden = true;
  els.emptyView.hidden = true;
  els.courseView.hidden = false;
  if (els.utFooter) els.utFooter.hidden = true;
  els.courseView.classList.remove("detail-open");
  els.courseView.classList.remove("no-right");
  els.backButton.hidden = false;
  setTopDownloadVisible(true);
  els.mainArea.classList.add("course-open");
  els.pageTitle.textContent = `${state.currentCourse.course_code || state.currentCourse.name || `Course ${courseId}`} > Home`;
  els.pageSubtitle.textContent = state.currentCourse.name || "";
  els.courseTerm.textContent = state.currentCourse.term || state.currentCourse.state || "";
  els.openOriginalButton.onclick = () => showDownloadCommandPanel();
  if (els.downloadCourseTop) {
    els.downloadCourseTop.onclick = () => showDownloadCommandPanel();
  }

  renderCourseNav();
  renderExternalLinks();
  renderCourseArchiveStatus();
  renderModules();
  renderAnnouncements();
  renderFiles();
  renderPages();
  renderAssignments();
  activateHomePanel();
}

function placeholderCourse(course) {
  return {
    id: course.id,
    name: displayCourseName(course),
    course_code: course.course_code || "",
    term: course.term || "",
    home_url: course.home_url || "",
    modules: [
      {
        name: "Getting Started",
        items: [
          { title: "Course content has not been archived yet", type: "SubHeader" },
          { title: "Run sync_quercus.py for this course to populate documents", type: "Page" },
        ],
      },
    ],
    pages: [],
    files: [],
    announcements: [],
    assignments: [],
    grades: null,
    quizzes: [],
    discussions: [],
    tabs: [],
  };
}

function renderCourseNav() {
  els.courseTabs.innerHTML = "";
  const tabs = normalizedCourseTabs();
  for (const tab of tabs) {
    const button = document.createElement("button");
    const label = tab.label || labelForTab(tab.id);
    button.className = "course-link";
    button.dataset.nav = tab.id || normalizeText(label);
    button.textContent = label;
    button.addEventListener("click", () => handleCourseTab(tab, label));
    els.courseTabs.appendChild(button);
  }
}

function normalizedCourseTabs() {
  const rawTabs = (state.currentCourse.tabs || []).filter(tab => tab && tab.id && tab.label);
  if (rawTabs.length) return rawTabs;
  const tabs = [{ id: "home", label: "Home", html_url: state.currentCourse.home_url }];
  if (state.currentCourse.syllabus) tabs.push({ id: "syllabus", label: "Syllabus" });
  if ((state.currentCourse.announcements || []).length) tabs.push({ id: "announcements", label: "Announcements" });
  if ((state.currentCourse.modules || []).length) tabs.push({ id: "modules", label: "Modules" });
  if ((state.currentCourse.pages || []).length) tabs.push({ id: "pages", label: "Pages" });
  if ((state.currentCourse.assignments || []).length) tabs.push({ id: "assignments", label: "Assignments" });
  if ((state.currentCourse.quizzes || []).length) tabs.push({ id: "quizzes", label: "Quizzes" });
  if ((state.currentCourse.discussions || []).length) tabs.push({ id: "discussions", label: "Discussions" });
  tabs.push({ id: "grades", label: "Grades" });
  return tabs;
}

function handleCourseTab(tab, label) {
  const tabId = tab.id || "";
  const explicitPage = findPageByKey(tab.resolved_page_key) || findPageByKey(tab.resolved_local_path);
  const localPage = explicitPage || findPageForCourseTab(tab, label);
  if (localPage && tabId !== "home" && tabId !== "syllabus") {
    return openPageDetail(localPage, { activeNav: tabId });
  }
  if (tabId === "home") return activateHomePanel();
  if (tabId === "syllabus") return showSyllabusPanel(tabId);
  if (tabId === "announcements") return activatePanel("announcements", tabId);
  if (tabId === "modules") return activatePanel("modules", tabId);
  if (tabId === "files") return activatePanel("files", tabId);
  if (tabId === "pages" || tabId === "wiki") return activatePanel("pages", tabId);
  if (tabId === "assignments") return activatePanel("assignments", tabId);
  if (tabId === "grades") return activatePanel("grades", tabId);
  if (tabId === "quizzes") return activatePanel("quizzes", tabId);
  if (tabId === "discussions") return activatePanel("discussions", tabId);
  if (tabId === "people") {
    return showEmptyCoursePanel(label, tabId);
  }
  if (tab.resolved_file_id || tab.resolved_file_href) {
    const file = findFileByHref(tab.resolved_file_href || "") || (state.currentCourse.files || [])
      .find(candidate => tab.resolved_file_id && Number(candidate.id) === Number(tab.resolved_file_id));
    return previewFile(file || {
      id: tab.resolved_file_id,
      display_name: label,
      html_url: tab.resolved_file_href || tab.html_url,
      url: tab.resolved_file_href,
    });
  }
  if (tabId.startsWith("context_external_tool_") || tab.html_url) {
    const targetUrl = tab.resolved_external_url || tab.launch_url || tab.html_url;
    setCourseNavActive(tabId);
    return openItemDetail({
      title: label,
      type: "External Tool",
      url: targetUrl,
      original_url: tab.html_url,
      external_kind: tab.external_kind || classifyExternalKind(label, targetUrl, "ExternalTool"),
      meta: "Recorded as a course tab. Internal external-tool content is not copied.",
      activeNav: tabId,
    });
  }
  showEmptyCoursePanel(label, tabId || label);
}

function labelForTab(tabId) {
  return {
    home: "Home",
    syllabus: "Syllabus",
    announcements: "Announcements",
    modules: "Modules",
    files: "Files",
    pages: "Pages",
    wiki: "Pages",
    assignments: "Assignments",
    grades: "Grades",
    quizzes: "Quizzes",
    discussions: "Discussions",
    people: "People",
  }[tabId] || tabId || "Link";
}

function renderExternalLinks() {
  const externals = [];

  for (const module of state.currentCourse.modules || []) {
    for (const item of module.items || []) {
      if (item.display_only) {
        externals.push({ label: item.title, html_url: item.external_url || item.html_url });
      }
    }
  }

  els.externalLinks.innerHTML = "";
  for (const item of dedupeLinks(externals)) {
    const button = document.createElement("button");
    const title = item.label || "External Tool";
    const url = item.html_url || item.external_url || "";
    button.className = "external-entry";
    button.textContent = title;
    button.addEventListener("click", () => openItemDetail({
      title,
      type: "External Tool",
      url,
      external_kind: classifyExternalKind(title, url, "ExternalTool"),
      meta: "Recorded as a course link. Internal Piazza/MarkUs content is not copied.",
    }));
    els.externalLinks.appendChild(button);
  }
}

function renderCourseArchiveStatus() {
  const tools = document.querySelector(".course-status");
  if (!tools || !state.currentCourse) return;
  const fileCount = (state.currentCourse.files || []).length;
  const downloadedCount = (state.currentCourse.files || []).filter(file => file.local_path).length;
  const pageCount = (state.currentCourse.pages || []).length + (state.currentCourse.syllabus ? 1 : 0);
  const announcementCount = (state.currentCourse.announcements || []).length;
  tools.innerHTML = `
    <h2>To Do</h2>
    <p>Nothing for now</p>
    <h2>Recent Feedback</h2>
    <p>Nothing for now</p>
    <h2>Archive Status</h2>
    <div class="archive-status-box">
      <div><strong>${downloadedCount}</strong><span>Downloaded files</span></div>
      <div><strong>${fileCount}</strong><span>Known files</span></div>
      <div><strong>${pageCount}</strong><span>Pages</span></div>
      <div><strong>${announcementCount}</strong><span>Announcements</span></div>
    </div>
  `;
}

function renderModules() {
  els.panelModules.innerHTML = "";
  const modules = state.currentCourse.modules || [];
  if (!modules.length && (state.currentCourse.pages || []).length) {
    renderSyntheticPagesHome();
    return;
  }
  if (!modules.length && (state.currentCourse.assignments || []).length) {
    renderSyntheticAssignmentsHome();
    return;
  }
  for (const module of modules) {
    const block = document.createElement("section");
    block.className = "module";

    const header = document.createElement("button");
    header.className = "module-header";
    header.textContent = module.name || "Untitled Module";
    header.addEventListener("click", () => {
      const list = block.querySelector(".module-items");
      list.hidden = !list.hidden;
    });

    const list = document.createElement("div");
    list.className = "module-items";
    for (const item of module.items || []) {
      list.appendChild(renderModuleItem(item));
    }

    block.append(header, list);
    els.panelModules.appendChild(block);
  }
}

function renderSyntheticPagesHome() {
  const block = document.createElement("section");
  block.className = "module";
  const header = document.createElement("button");
  header.className = "module-header";
  header.textContent = "Pages";
  const list = document.createElement("div");
  list.className = "module-items";
  for (const page of state.currentCourse.pages || []) {
    list.appendChild(renderModuleItem({
      title: page.title,
      type: "Page",
      page,
    }));
  }
  block.append(header, list);
  els.panelModules.appendChild(block);
}

function renderSyntheticAssignmentsHome() {
  const block = document.createElement("section");
  block.className = "module";
  const header = document.createElement("button");
  header.className = "module-header";
  header.textContent = "Assignments";
  const list = document.createElement("div");
  list.className = "module-items";
  for (const assignment of state.currentCourse.assignments || []) {
    list.appendChild(renderModuleItem({
      title: assignment.name,
      type: "Assignment",
      html_url: assignment.html_url,
      assignment,
    }));
  }
  block.append(header, list);
  els.panelModules.appendChild(block);
}

function renderModuleItem(item) {
  const row = document.createElement("div");
  row.className = "item-row";
  row.style.paddingLeft = `${14 + Number(item.indent || 0) * 22}px`;

  const symbol = document.createElement("span");
  symbol.className = `type-icon ${typeIconClass(item.type)}`;
  symbol.setAttribute("aria-hidden", "true");

  const button = document.createElement("button");
  button.innerHTML = `
    <strong>${escapeHtml(item.title || "Untitled")}</strong>
    <span class="item-meta">${escapeHtml(item.type || "")}</span>
  `;
  button.addEventListener("click", () => previewItem(item));

  const badge = document.createElement("span");
  badge.className = "badge";
  badge.textContent = item.display_only ? "Link" : item.local_path ? "Local" : item.type || "Item";

  row.append(symbol, button, badge);
  return row;
}

function renderFiles() {
  renderSimplePanel(
    els.panelFiles,
    state.currentCourse.files || [],
    file => file.display_name || file.filename || `File ${file.id}`,
    file => file.local_path ? "Downloaded" : file.warning ? "Unavailable" : "Metadata",
    previewFile,
  );
}

function renderAnnouncements() {
  renderSimplePanel(
    els.panelAnnouncements,
    state.currentCourse.announcements || [],
    item => item.title || "Untitled Announcement",
    item => [formatDate(item.posted_at || item.delayed_post_at), item.user_name].filter(Boolean).join(" | "),
    previewAnnouncement,
  );
}

function renderPages() {
  renderSimplePanel(
    els.panelPages,
    state.currentCourse.pages || [],
    page => page.title || "Untitled Page",
    page => page.local_path ? "Archived page" : page.warning ? "Unavailable" : "Page",
    previewPage,
  );
}

function renderAssignments() {
  renderSimplePanel(
    els.panelAssignments,
    state.currentCourse.assignments || [],
    item => item.name || "Untitled Assignment",
    item => [formatDate(item.due_at), item.points_possible ? `${item.points_possible} pts` : ""].filter(Boolean).join(" | "),
    previewAssignment,
  );
}

function renderQuizzes() {
  renderSimplePanel(
    els.panelQuizzes,
    state.currentCourse.quizzes || [],
    item => item.title || "Untitled Quiz",
    item => [formatDate(item.due_at), item.points_possible !== null && item.points_possible !== undefined ? `${item.points_possible} pts` : "", item.question_count ? `${item.question_count} questions` : ""].filter(Boolean).join(" | "),
    previewQuiz,
  );
}

function renderDiscussions() {
  renderSimplePanel(
    els.panelDiscussions,
    state.currentCourse.discussions || [],
    item => item.title || "Untitled Discussion",
    item => [formatDate(item.posted_at || item.delayed_post_at), item.user_name].filter(Boolean).join(" | "),
    previewDiscussion,
  );
}

function renderGrades() {
  const grades = state.currentCourse.grades || {};
  const groups = grades.groups || [];
  const summary = grades.summary || {};
  els.panelGrades.innerHTML = `
    <section class="grades-panel">
      <div class="grades-summary">
        <div><span>Total</span><strong>${formatGradePercent(summary.percent ?? summary.current_score ?? summary.final_score)}</strong></div>
        <div><span>Points</span><strong>${formatPoints(summary.earned_points, summary.possible_points)}</strong></div>
        <div><span>Graded</span><strong>${escapeHtml(summary.graded_count ?? 0)} / ${escapeHtml(summary.assignment_count ?? 0)}</strong></div>
      </div>
      ${grades.warning ? `<p class="grade-warning">${escapeHtml(grades.warning)}</p>` : ""}
      ${groups.length ? groups.map(renderGradeGroup).join("") : `<div class="empty-course-panel"><h2>Grades</h2><p>No grade items archived for this course yet. Re-run metadata sync for this course.</p></div>`}
    </section>
  `;
}

function renderGradeGroup(group) {
  const assignments = group.assignments || [];
  return `
    <section class="grade-group">
      <header>
        <h2>${escapeHtml(group.name || "Assignments")}</h2>
        <span>${group.group_weight !== null && group.group_weight !== undefined ? `${escapeHtml(group.group_weight)}% of grade` : formatGradePercent(group.percent)}</span>
      </header>
      <div class="grade-table">
        <div class="grade-row grade-head">
          <span>Name</span><span>Due</span><span>Status</span><span>Score</span><span>Out of</span>
        </div>
        ${assignments.map(renderGradeRow).join("") || `<div class="grade-row"><span>No assignments in this group</span><span></span><span></span><span></span><span></span></div>`}
      </div>
    </section>
  `;
}

function renderGradeRow(item) {
  const submission = item.submission || {};
  return `
    <div class="grade-row">
      <span>${escapeHtml(item.name || "Untitled")}</span>
      <span>${escapeHtml(formatDate(item.due_at) || "")}</span>
      <span>${escapeHtml(item.status || "")}</span>
      <span>${escapeHtml(submission.grade || formatNumber(submission.score) || "")}</span>
      <span>${escapeHtml(formatNumber(item.points_possible) || "")}</span>
    </div>
  `;
}

function renderSimplePanel(container, items, titleFn, metaFn, clickFn) {
  container.innerHTML = "";
  const wrap = document.createElement("div");
  wrap.className = "table-list";

  if (!items.length) {
    wrap.innerHTML = `<div class="table-row"><span>No items archived</span></div>`;
    container.appendChild(wrap);
    return;
  }

  for (const item of items) {
    const row = document.createElement("div");
    row.className = "table-row";
    const button = document.createElement("button");
    button.innerHTML = `
      <strong>${escapeHtml(titleFn(item))}</strong>
      <span class="item-meta">${escapeHtml(metaFn(item) || "")}</span>
    `;
    button.addEventListener("click", () => clickFn(item));
    const badge = document.createElement("span");
    badge.className = "badge";
    badge.textContent = item.local_path ? "Local" : "Link";
    row.append(button, badge);
    wrap.appendChild(row);
  }
  container.appendChild(wrap);
}

function previewItem(item) {
  const resolvedPage = findPageByKey(item.resolved_page_key);
  if (resolvedPage) return previewPage(resolvedPage);
  if (item.page) return previewPage(item.page);
  if (item.resolved_file_id || item.resolved_file_href) {
    const file = (state.currentCourse.files || []).find(candidate => {
      if (item.resolved_file_id && Number(candidate.id) === Number(item.resolved_file_id)) return true;
      return item.resolved_file_href && findFileByHref(item.resolved_file_href) === candidate;
    });
    return previewFile(file || {
      id: item.resolved_file_id,
      display_name: item.title,
      html_url: item.resolved_file_href || item.html_url,
      url: item.resolved_file_href,
    });
  }
  if (item.type === "File" && item.content_id) {
    const file = (state.currentCourse.files || []).find(candidate => candidate.id === item.content_id);
    return previewFile(file || {
      id: item.content_id,
      display_name: item.title,
      html_url: item.html_url,
      api_url: item.api_url,
    });
  }
  if (item.type === "Page" && !item.page) {
    return openItemDetail({
      title: item.title,
      type: "Page",
      url: item.html_url,
      meta: "This page has not been archived yet.",
    });
  }
  if (item.type === "Assignment") {
    const assignment = item.assignment || (state.currentCourse.assignments || [])
      .find(candidate => Number(candidate.id) === Number(item.content_id));
    return assignment ? previewAssignment(assignment) : openItemDetail({
      title: item.title,
      type: "Assignment",
      url: item.html_url,
    });
  }
  if (item.type === "Quiz") {
    const quiz = item.quiz || (state.currentCourse.quizzes || [])
      .find(candidate => Number(candidate.id) === Number(item.content_id));
    return quiz ? previewQuiz(quiz) : openItemDetail({
      title: item.title,
      type: "Quiz",
      url: item.html_url,
      meta: "Quiz metadata is preserved locally; attempts are not archived.",
    });
  }
  if (item.type === "Discussion") {
    const discussion = item.discussion || (state.currentCourse.discussions || [])
      .find(candidate => Number(candidate.id) === Number(item.content_id));
    return discussion ? previewDiscussion(discussion) : openItemDetail({
      title: item.title,
      type: "Discussion",
      url: item.html_url,
    });
  }
  if (item.resolved_external_url || item.external_url || item.html_url) {
    const targetUrl = item.resolved_external_url || item.external_url || item.html_url;
    return openItemDetail({
      title: item.title,
      type: item.type || "External item",
      url: targetUrl,
      original_url: item.html_url,
      external_kind: item.external_kind || classifyExternalKind(item.title, targetUrl, item.type),
    });
  }
  showViewer(item.title || "Item", null, "This item was recorded, but no local preview is available.");
}

function previewFile(file) {
  if (!file) return;
  const title = file.display_name || file.filename || `File ${file.id}`;
  openFileOverlay({
    file_id: file.id,
    title,
    local_path: file.local_path,
    href: file.local_path ? `/archive/${file.local_path}` : null,
    original_href: file.html_url || file.url || file.api_url,
  });
}

function previewPage(page) {
  if (!page) return;
  return openPageDetail(page);
}

function openPageDetail(page, options = {}) {
  const title = page.title || "Page";
  setCourseLocation({
    kind: "page",
    key: pageKey(page),
    activeNav: options.activeNav || "",
  });
  if (!page.local_path) {
    openItemDetail({
      title,
      type: "Page",
      url: page.html_url,
      meta: page.warning || "This page was not archived.",
    });
    return;
  }
  const url = `/archive/${page.local_path}`;
  const bodyHtml = page.body || "";
  const showTitle = !bodyStartsWithTitle(bodyHtml, title);
  if (options.activeNav) setCourseNavActive(options.activeNav);
  else clearCourseNavActive();
  hideCoursePanels();
  els.courseView.classList.add("detail-open");
  els.courseView.classList.remove("no-right");
  setCourseActionsVisible(false);
  els.panelPageDetail.hidden = false;
  els.pageTitle.textContent = `${state.currentCourse.course_code || state.currentCourse.name || ""} > Pages > ${title}`;
  els.panelPageDetail.innerHTML = `
    <div class="page-detail canvas-page-view">
      ${showTitle ? `<h2>${escapeHtml(title)}</h2>` : ""}
      <div class="canvas-html-body">${prepareCanvasHtml(bodyHtml) || `<iframe class="page-detail-frame" src="${url}" title="${escapeHtml(title)}"></iframe>`}</div>
      <div class="page-nav">
        <button type="button">‹ Previous</button>
        <button type="button">Next ›</button>
      </div>
    </div>
  `;
  bindCanvasHtmlLinks(els.panelPageDetail, page.linked_files || []);
  showViewer("Preview", null, "Select a file link from the page.");
}

function previewExternal(title, url) {
  openItemDetail({ title, type: "External Link", url });
}

function openItemDetail(item) {
  const title = item.title || "Untitled";
  const externalKind = item.external_kind || classifyExternalKind(title, item.url, item.type);
  setCourseLocation({
    kind: "item",
    item: {
      title,
      type: item.type || "Item",
      url: item.url || "",
      original_url: item.original_url || "",
      external_kind: externalKind,
      meta: item.meta || "",
      activeNav: item.activeNav || "",
    },
  });
  if (item.activeNav) setCourseNavActive(item.activeNav);
  else clearCourseNavActive();
  hideCoursePanels();
  els.courseView.classList.add("detail-open");
  els.courseView.classList.remove("no-right");
  setCourseActionsVisible(false);
  els.panelPageDetail.hidden = false;
  els.pageTitle.textContent = `${state.currentCourse.course_code || state.currentCourse.name || ""} > ${item.type || "Item"} > ${title}`;
  els.panelPageDetail.innerHTML = `
    <div class="item-detail">
      <div class="page-detail-breadcrumb">${escapeHtml(state.currentCourse.course_code || state.currentCourse.name || "")} &gt; ${escapeHtml(item.type || "Item")}</div>
      <h2>${escapeHtml(title)}</h2>
      ${item.meta ? `<p class="item-detail-meta">${escapeHtml(item.meta)}</p>` : ""}
      ${item.url ? renderArchivedExternalRecord({ ...item, external_kind: externalKind }) : `<p>No original link archived for this item.</p>`}
    </div>
  `;
  bindCanvasHtmlLinks(els.panelPageDetail, []);
  showViewer(title, null, item.url ? "External item recorded locally. Open the original only if you still have access." : "No preview available.");
}

function renderArchivedExternalRecord(item) {
  const originalUrl = absoluteCanvasUrl(item.url);
  const canvasWrapperUrl = item.original_url ? absoluteCanvasUrl(item.original_url) : "";
  const kind = externalKindLabel(item.external_kind);
  return `
    <div class="external-record">
      <div class="external-record-icon ${escapeHtml(iconClassForExternalKind(item.external_kind))}" aria-hidden="true"></div>
      <div>
        <h3>${escapeHtml(kind)}</h3>
        <p>This entry is preserved as a local record. External tool content is intentionally not copied; Canvas pages and local files should be opened through the archive navigation instead.</p>
        <dl>
          <div><dt>Status</dt><dd>Local link record</dd></div>
          <div><dt>Target URL</dt><dd>${originalUrl ? `<a data-original-link="true" href="${escapeHtml(originalUrl)}" target="_blank" rel="noreferrer">${escapeHtml(originalUrl)}</a>` : "No URL recorded"}</dd></div>
          ${canvasWrapperUrl && canvasWrapperUrl !== originalUrl ? `<div><dt>Canvas wrapper</dt><dd>${escapeHtml(canvasWrapperUrl)}</dd></div>` : ""}
        </dl>
      </div>
    </div>
  `;
}

function bindCanvasHtmlLinks(root, linkedFiles = []) {
  for (const link of root.querySelectorAll("a[href]")) {
    if (link.dataset.originalLink === "true") continue;
    const href = link.getAttribute("href") || "";
    if (!href || href.startsWith("#")) continue;
    const match = matchLinkedFile(href, linkedFiles, link.textContent || "");
    const localRoute = match ? null : resolveLocalCanvasLink(link);
    link.dataset.archiveRoute = match
      ? "file"
      : localRoute
        ? "local"
        : looksLikeFileHref(href)
          ? "file"
          : "external";
    link.classList.add(
      !match && !looksLikeFileHref(href) && !localRoute
        ? "canvas-external-link"
        : match || looksLikeFileHref(href)
          ? "canvas-file-link"
          : "canvas-internal-link",
    );
  }
  root.onclick = event => {
    const link = event.target.closest?.("a[href]");
    if (!link || !root.contains(link) || link.dataset.originalLink === "true") return;
    const href = link.getAttribute("href") || "";
    if (!href || href.startsWith("#")) return;
    event.preventDefault();
    const match = matchLinkedFile(href, linkedFiles, link.textContent || "");
    const localRoute = match ? null : resolveLocalCanvasLink(link);
    if (localRoute) {
      localRoute();
      return;
    }
    if (match || looksLikeFileHref(href)) {
      openFileOverlay(match || { title: link.textContent || href, href });
      return;
    }
    if (shouldOpenDirectExternal(href)) {
      window.open(absoluteCanvasUrl(href), "_blank", "noreferrer");
      return;
    }
    openItemDetail({
      title: link.textContent || href,
      type: "External Link",
      url: href,
      external_kind: classifyExternalKind(link.textContent || href, href, "ExternalUrl"),
    });
  };
}

function matchLinkedFile(href, linkedFiles, text) {
  const hrefId = extractFileId(href);
  const linked = linkedFiles.find(file => {
    if (hrefId && Number(file.file_id) === hrefId) return true;
    if (file.href && normalizeUrl(file.href) === normalizeUrl(href)) return true;
    return text && file.title && normalizeText(file.title) === normalizeText(text);
  });
  const matchingFile = findFileByHref(href, text);
  if (!linked && !matchingFile) return null;
  return {
    ...(linked || {}),
    file_id: linked?.file_id || matchingFile?.id || hrefId,
    title: linked?.title || matchingFile?.display_name || matchingFile?.filename || text,
    local_path: matchingFile?.local_path,
    href: matchingFile?.local_path ? `/archive/${matchingFile.local_path}` : linked?.href || matchingFile?.html_url || matchingFile?.url || href,
    original_href: matchingFile?.html_url || matchingFile?.url || linked?.href || href,
  };
}

function findFileByHref(href, text = "") {
  const hrefId = extractFileId(href);
  const normalized = normalizeUrl(href);
  const tailName = lastPathName(href);
  const textName = normalizeFileName(text);
  return (state.currentCourse.files || []).find(file => {
    if (hrefId && Number(file.id) === hrefId) return true;
    for (const key of ["html_url", "url", "preview_url", "api_url", "external_url"]) {
      if (file[key] && normalizeUrl(file[key]) === normalized) return true;
    }
    const display = normalizeFileName(file.display_name || file.filename || "");
    if (tailName && display && display === tailName) return true;
    if (textName && display && display === textName) return true;
    return false;
  }) || null;
}

function extractFileId(value) {
  const match = String(value || "").match(/\/files\/(\d+)|files%2F(\d+)|file_id=(\d+)/);
  return match ? Number(match[1] || match[2] || match[3]) : null;
}

function looksLikeFileHref(value) {
  return /\.(pdf|docx?|pptx?|xlsx?|csv|zip|txt|py|r|jpg|jpeg|png|gif|mp4|mov|m4v|mp3|wav)(\?|#|$)/i.test(value || "");
}

function shouldOpenDirectExternal(value) {
  const url = String(value || "");
  if (/^mailto:/i.test(url)) return true;
  if (!/^(https?:)?\/\//i.test(url)) return false;
  return !isCanvasUrl(url);
}

function isCanvasUrl(value) {
  const url = String(value || "");
  const base = canvasBaseUrl();
  try {
    const parsed = new URL(url.startsWith("//") ? `https:${url}` : url, base);
    const baseParsed = new URL(base);
    return parsed.hostname === baseParsed.hostname;
  } catch {
    return false;
  }
}

function resolveLocalCanvasLink(link) {
  const href = link.getAttribute("href") || "";
  const endpoint = link.dataset.apiEndpoint || "";
  const text = link.textContent || "";
  const target = endpoint || href;
  const globalRoute = resolveGlobalCanvasLink(target);
  if (globalRoute) return globalRoute;

  const courseId = extractCourseId(target) || extractCourseId(href);
  if (courseId && state.currentCourse && Number(courseId) !== Number(state.currentCourse.id)) {
    const course = (state.manifest?.courses || []).find(item => Number(item.id) === Number(courseId));
    if (course) return () => openCourse(course.id);
  }

  const page = findPageByHref(endpoint, text) || findPageByHref(href, text);
  if (page) return () => previewPage(page);

  if (/\/courses\/\d+\/assignments\/syllabus(\/|\?|#|$)/.test(normalizeUrl(target))) {
    return () => {
      showSyllabusPanel("syllabus");
      scrollToCanvasHash(target);
    };
  }

  const assignmentId = extractPathId(target, "assignments");
  if (assignmentId) {
    const assignment = (state.currentCourse.assignments || []).find(item => Number(item.id) === assignmentId);
    if (assignment) {
      return () => previewAssignment(assignment);
    }
  }

  const topicId = extractPathId(target, "discussion_topics");
  if (topicId) {
    const announcement = (state.currentCourse.announcements || []).find(item => Number(item.id) === topicId);
    if (announcement) return () => previewAnnouncement(announcement);
    const discussion = (state.currentCourse.discussions || []).find(item => Number(item.id) === topicId);
    if (discussion) return () => previewDiscussion(discussion);
    return () => showEmptyCoursePanel(text || "Discussion", "discussions", "This discussion link was preserved, but the discussion content is not archived locally.");
  }

  const quizId = extractPathId(target, "quizzes");
  if (quizId) {
    const quiz = (state.currentCourse.quizzes || []).find(item => Number(item.id) === quizId);
    if (quiz) return () => previewQuiz(quiz);
    return () => showEmptyCoursePanel(text || "Quiz", "quizzes", "This quiz link was preserved, but quiz attempts and live quiz content are not archived locally.");
  }

  const moduleItemId = extractModuleItemId(target);
  if (moduleItemId) {
    const moduleItem = findModuleItem(moduleItemId);
    if (moduleItem) return () => previewItem(moduleItem);
  }

  const externalToolId = extractPathId(target, "external_tools");
  if (externalToolId) {
    const tab = (state.currentCourse.tabs || [])
      .find(item => String(item.id || "").endsWith(`_${externalToolId}`) || normalizeUrl(item.html_url) === normalizeUrl(href));
    if (tab) {
      const tabLabel = tab.label || text || "External Tool";
      const tabPage = findPageByKey(tab.resolved_page_key) || findPageByKey(tab.resolved_local_path) || findPageForCourseTab(tab, tabLabel);
      if (tabPage) return () => openPageDetail(tabPage, { activeNav: tab.id || "" });
      const targetUrl = tab.resolved_external_url || tab.launch_url || tab.html_url || href;
      return () => openItemDetail({
        title: tabLabel,
        type: "External Tool",
        url: targetUrl,
        original_url: tab.html_url || href,
        external_kind: tab.external_kind || classifyExternalKind(tabLabel, targetUrl, "ExternalTool"),
        meta: "Recorded as a course tab. Internal external-tool content is not copied.",
        activeNav: tab.id || "",
      });
    }
  }

  const tabRoute = resolveCourseTabRoute(target, text);
  if (tabRoute) return tabRoute;

  if (/\/modules(\/|\?|#|$)/.test(normalizeUrl(target))) {
    return () => activatePanel("modules");
  }
  if (/\/announcements(\/|\?|#|$)/.test(normalizeUrl(target))) {
    return () => activatePanel("announcements");
  }
  if (/\/assignments(\/|\?|#|$)/.test(normalizeUrl(target))) {
    return () => activatePanel("assignments");
  }
  if (/\/files(\/|\?|#|$)/.test(normalizeUrl(target))) {
    return () => activatePanel("files");
  }
  if (/\/pages(\/|\?|#|$)/.test(normalizeUrl(target))) {
    return () => activatePanel("pages");
  }
  if (new RegExp(`/courses/${state.currentCourse.id}(/|\\?|#|$)`).test(normalizeUrl(target))) {
    return () => activateHomePanel();
  }
  return null;
}

function resolveGlobalCanvasLink(value) {
  const path = canvasPath(value);
  if (!path) return null;
  if (/\/calendar(\/|\?|#|$)/.test(path)) return () => showGlobalTool("calendar");
  if (/\/conversations(\/|\?|#|$)|\/inbox(\/|\?|#|$)/.test(path)) return () => showGlobalTool("inbox");
  if (/\/profile\/settings(\/|\?|#|$)|\/users\/self(\/|\?|#|$)/.test(path)) return () => showGlobalTool("account");
  if (/\/courses(\/|\?|#|$)/.test(path) && !/\/courses\/\d+/.test(path)) return () => renderCoursesPage();
  return null;
}

function resolveCourseTabRoute(value, text = "") {
  const path = canvasPath(value);
  const label = normalizeText(text);
  const tab = (state.currentCourse.tabs || []).find(item => {
    const tabId = String(item.id || "");
    const tabLabel = normalizeText(item.label || "");
    if (label && tabLabel && label === tabLabel) return true;
    if (item.html_url && normalizeUrl(item.html_url) === normalizeUrl(value)) return true;
    return tabId && new RegExp(`/${tabId}(/|\\?|#|$)`).test(path);
  });
  if (tab) {
    return () => handleCourseTab(tab, tab.label || text || labelForTab(tab.id));
  }
  if (/\/grades(\/|\?|#|$)/.test(path)) return () => activatePanel("grades");
  if (/\/quizzes(\/|\?|#|$)/.test(path)) return () => activatePanel("quizzes");
  if (/\/discussion_topics(\/|\?|#|$)|\/discussions(\/|\?|#|$)/.test(path)) return () => activatePanel("discussions");
  if (/\/users(\/|\?|#|$)/.test(path)) return () => showEmptyCoursePanel("People", "people", "People roster content is not archived locally.");
  return null;
}

function extractCourseId(value) {
  const match = normalizeUrl(value).match(/\/courses\/(\d+)/);
  return match ? Number(match[1]) : null;
}

function extractModuleItemId(value) {
  const match = normalizeUrl(value).match(/\/modules\/items\/(\d+)|module_item_id=(\d+)/);
  return match ? Number(match[1] || match[2]) : null;
}

function findModuleItem(itemId) {
  for (const module of state.currentCourse.modules || []) {
    const item = (module.items || []).find(candidate => Number(candidate.id) === Number(itemId));
    if (item) return item;
  }
  return null;
}

function findPageByHref(value, text = "") {
  if (!value && !text) return null;
  const slug = extractPageSlug(value);
  const normalized = normalizeUrl(value);
  const routeText = normalizeRouteText(text);
  return (state.currentCourse.pages || []).find(page => {
    if (normalized && page.html_url && normalizeUrl(page.html_url) === normalized) return true;
    if (normalized && Array.isArray(page.aliases) && page.aliases.some(alias => normalizeUrl(alias) === normalized)) return true;
    if (slug && extractPageSlug(page.html_url) === slug) return true;
    if (!routeText || !page.title) return false;
    const pageText = normalizeRouteText(page.title);
    return pageText === routeText || fuzzyRouteMatch(pageText, routeText);
  }) || null;
}

function scrollToCanvasHash(value) {
  const hash = String(value || "").split("#")[1];
  if (!hash) return;
  window.setTimeout(() => {
    const id = decodeURIComponent(hash);
    const target = document.getElementById(id) || document.querySelector(`[name="${cssEscape(id)}"]`);
    if (target) target.scrollIntoView({ block: "start" });
  }, 0);
}

function cssEscape(value) {
  if (window.CSS?.escape) return CSS.escape(value);
  return String(value).replace(/["\\]/g, "\\$&");
}

function findPageForCourseTab(tab, label) {
  return findPageByHref(tab?.html_url || "", label)
    || findPageByHref("", label)
    || (state.currentCourse.pages || []).find(page => {
      const title = normalizeRouteText(page.title || "");
      const tabLabel = normalizeRouteText(label || tab?.label || "");
      return title && tabLabel && (title === tabLabel || fuzzyRouteMatch(title, tabLabel));
    })
    || null;
}

function pageKey(page) {
  return page?.html_url || page?.local_path || page?.title || "";
}

function findPageByKey(key) {
  if (!key) return null;
  return (state.currentCourse.pages || []).find(page => pageKey(page) === key)
    || findPageByHref(key)
    || null;
}

function extractPageSlug(value) {
  const match = String(value || "").match(/(?:^|\/)pages\/([^/?#]+)/);
  return match ? decodeURIComponent(match[1]) : "";
}

function extractPathId(value, segment) {
  const match = String(value || "").match(new RegExp(`/${segment}/(\\d+)`));
  return match ? Number(match[1]) : null;
}

function prepareCanvasHtml(html) {
  const wrapper = document.createElement("div");
  wrapper.innerHTML = html || "";

  for (const embed of wrapper.querySelectorAll("iframe[src], embed[src], object[data]")) {
    embed.replaceWith(renderExternalEmbedPlaceholder(embed));
  }
  for (const video of wrapper.querySelectorAll("video")) {
    const src = video.getAttribute("src") || video.querySelector("source[src]")?.getAttribute("src") || "";
    if (isRemoteUrl(src)) video.replaceWith(renderExternalEmbedPlaceholder(video, src));
  }
  return wrapper.innerHTML;
}

function renderExternalEmbedPlaceholder(element, forcedUrl = "") {
  const source = forcedUrl || element.getAttribute("src") || element.getAttribute("data") || "";
  const title = element.getAttribute("title") || element.getAttribute("aria-label") || "Embedded content";
  const absoluteUrl = absoluteCanvasUrl(source);
  const kind = classifyExternalKind(title, absoluteUrl, "ExternalTool");
  const placeholder = document.createElement("div");
  placeholder.className = "external-embed-placeholder";
  placeholder.innerHTML = `
    <span class="external-record-icon ${escapeHtml(iconClassForExternalKind(kind))}" aria-hidden="true"></span>
    <div>
      <strong>${escapeHtml(externalKindLabel(kind))}</strong>
      <p>This embedded item was preserved as a link record instead of loading the remote page automatically.</p>
      ${absoluteUrl ? `<a data-original-link="true" href="${escapeHtml(absoluteUrl)}" target="_blank" rel="noreferrer">${escapeHtml(absoluteUrl)}</a>` : ""}
    </div>
  `;
  return placeholder;
}

function isRemoteUrl(value) {
  return /^(https?:)?\/\//i.test(String(value || ""));
}

function normalizeUrl(value) {
  const raw = String(value || "").trim();
  if (!raw) return "";
  if (/^(mailto:|tel:|javascript:)/i.test(raw)) return raw.split("#")[0];
  try {
    const base = canvasBaseUrl();
    const baseParsed = new URL(base);
    const parsed = new URL(raw.startsWith("//") ? `${baseParsed.protocol}${raw}` : raw, base);
    const withoutHash = parsed.hostname === baseParsed.hostname
      ? `${parsed.pathname}${parsed.search}`
      : parsed.href.split("#")[0];
    return decodeURIComponent(withoutHash);
  } catch {
    return decodeURIComponent(raw.split("#")[0]);
  }
}

function canvasPath(value) {
  const raw = normalizeUrl(value);
  if (!raw) return "";
  try {
    const parsed = raw.startsWith("http://") || raw.startsWith("https://")
      ? new URL(raw)
      : new URL(raw, canvasBaseUrl());
    return decodeURIComponent(`${parsed.pathname}${parsed.search}`);
  } catch {
    return decodeURIComponent(raw);
  }
}

function canvasBaseUrl() {
  return (state.manifest?.base_url || "https://q.utoronto.ca").replace(/\/$/, "");
}

function lastPathName(value) {
  const path = canvasPath(value).split("?")[0].split("#")[0];
  const name = path.split("/").filter(Boolean).pop() || "";
  return normalizeFileName(name);
}

function normalizeFileName(value) {
  return normalizeText(decodeURIComponent(String(value || ""))).replace(/\s+\[\d+\](?=\.[^.]+$)/, "");
}

function normalizeRouteText(value) {
  return normalizeText(value)
    .replace(/&/g, " and ")
    .replace(/\+/g, " ")
    .replace(/\//g, " and ")
    .replace(/[-_:;,.()[\]{}]+/g, " ")
    .replace(/\b(getting|help|in|for|the|a|an)\b/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function fuzzyRouteMatch(left, right) {
  if (!left || !right) return false;
  if (left === right) return true;
  if (left.length >= 8 && right.includes(left)) return true;
  if (right.length >= 8 && left.includes(right)) return true;
  return false;
}

function normalizeText(value) {
  return String(value || "").replace(/\s+/g, " ").trim().toLowerCase();
}

function bodyStartsWithTitle(html, title) {
  const wrapper = document.createElement("div");
  wrapper.innerHTML = html || "";
  const firstHeading = wrapper.querySelector("h1, h2, h3");
  if (!firstHeading) return false;
  return normalizeText(firstHeading.textContent) === normalizeText(title);
}

function openFileOverlay(file) {
  if (!file) return;
  const matchingFile = (state.currentCourse.files || []).find(candidate => candidate.id === file.file_id);
  const title = file.title || matchingFile?.display_name || "File preview";
  const localPath = file.local_path || matchingFile?.local_path;
  const localUrl = localPath ? `/archive/${localPath}` : null;
  const originalUrl = absoluteCanvasUrl(file.original_href || matchingFile?.html_url || file.href || matchingFile?.url || "");
  const fileId = file.file_id || matchingFile?.id || extractFileId(file.href || file.original_href || "");
  els.fileOverlayTitle.textContent = title;
  els.fileOverlayDownload.hidden = false;
  els.fileOverlayDownload.textContent = localUrl ? "Download" : "Original";
  els.fileOverlayDownload.href = localUrl || originalUrl || "#";
  if (!localUrl && !originalUrl) els.fileOverlayDownload.hidden = true;
  if (localUrl) {
    els.fileOverlayFrame.removeAttribute("srcdoc");
    els.fileOverlayFrame.src = localUrl;
    els.fileOverlay.classList.remove("missing-file");
  } else {
    els.fileOverlayFrame.src = "about:blank";
    els.fileOverlayFrame.srcdoc = missingFileDocument({ title, originalUrl, fileId });
    els.fileOverlay.classList.add("missing-file");
  }
  els.fileOverlay.hidden = false;
}

function missingFileDocument({ title, originalUrl, fileId }) {
  const courseId = state.currentCourse?.id || "";
  const command = courseId ? `python3 sync_quercus.py --course-id ${courseId} --download-files` : "python3 sync_quercus.py --download-files";
  return `
    <!doctype html>
    <html>
    <head>
      <meta charset="utf-8">
      <style>
        body{margin:0;font-family:Arial,Helvetica,sans-serif;background:#f4f6f8;color:#2f3b45;height:100vh;display:grid;place-items:center}
        main{width:min(680px,calc(100vw - 42px));background:white;border:1px solid #dfe3e7;padding:28px 32px;box-shadow:0 1px 3px rgba(0,0,0,.08)}
        h1{font-size:22px;font-weight:400;margin:0 0 10px}
        p{line-height:1.48;margin:0 0 16px;color:#5f6b75}
        dl{border-top:1px solid #e8eaed;margin:18px 0 0}
        div.row{display:grid;grid-template-columns:130px minmax(0,1fr);gap:12px;border-bottom:1px solid #e8eaed;padding:10px 0}
        dt{font-weight:700;color:#68737d}
        dd{margin:0;overflow-wrap:anywhere}
        code{display:block;background:#f6f7f8;border:1px solid #dfe3e7;padding:10px 12px;overflow-x:auto}
        a{color:#2f6fbf}
      </style>
    </head>
    <body>
      <main>
        <h1>File not downloaded yet</h1>
        <p>The archive knows about this Canvas file link, but the file is not present in the local folder yet. Run the course download command, refresh this page, then click the link again.</p>
        <code>${escapeHtml(command)}</code>
        <dl>
          <div class="row"><dt>File</dt><dd>${escapeHtml(title)}</dd></div>
          <div class="row"><dt>Canvas file id</dt><dd>${fileId ? escapeHtml(fileId) : "Not recorded"}</dd></div>
          <div class="row"><dt>Original URL</dt><dd>${originalUrl ? `<a href="${escapeHtml(originalUrl)}" target="_blank" rel="noreferrer">${escapeHtml(originalUrl)}</a>` : "No URL recorded"}</dd></div>
        </dl>
      </main>
    </body>
    </html>
  `;
}

function closeFileOverlay() {
  els.fileOverlay.hidden = true;
  els.fileOverlayFrame.src = "about:blank";
  els.fileOverlayFrame.removeAttribute("srcdoc");
}

function showDownloadCommandPanel() {
  if (!state.currentCourse) return;
  setCourseLocation({ kind: "download" });
  const command = `python3 sync_quercus.py --course-id ${state.currentCourse.id} --download-files`;
  hideCoursePanels();
  els.courseView.classList.add("detail-open");
  els.courseView.classList.remove("no-right");
  setCourseActionsVisible(false);
  clearCourseNavActive();
  els.panelPageDetail.hidden = false;
  els.pageTitle.textContent = `${state.currentCourse.course_code || state.currentCourse.name || state.currentCourse.id} > Download course content`;
  els.panelPageDetail.innerHTML = `
    <div class="empty-course-panel download-command-panel">
      <h2>Download course content</h2>
      <p>Run this from the project folder after setting QUERCUS_TOKEN. The downloader skips complete files and continues interrupted work.</p>
      <pre><code>${escapeHtml(command)}</code></pre>
    </div>
  `;
  hideViewerPreview();
}

function previewAnnouncement(item) {
  if (!item) return;
  const title = item.title || "Announcement";
  setCourseLocation({ kind: "announcement", id: item.id });
  clearCourseNavActive();
  const posted = formatDate(item.posted_at || item.delayed_post_at);
  const author = item.user_name ? `<div class="announcement-meta">${escapeHtml(item.user_name)}</div>` : "";
  const date = posted ? `<div class="announcement-meta">${escapeHtml(posted)}</div>` : "";
  const message = item.message || "<p>No message archived.</p>";
  hideCoursePanels();
  els.courseView.classList.add("detail-open");
  els.courseView.classList.remove("no-right");
  setCourseActionsVisible(false);
  els.panelPageDetail.hidden = false;
  els.pageTitle.textContent = `${state.currentCourse.course_code || state.currentCourse.name || ""} > Announcements > ${title}`;
  els.panelPageDetail.innerHTML = `
    <article class="announcement-preview">
      <h2>${escapeHtml(title)}</h2>
      ${author}${date}
      <div class="canvas-html-body">${prepareCanvasHtml(message)}</div>
    </article>
  `;
  bindCanvasHtmlLinks(els.panelPageDetail, item.linked_files || []);
  showViewer(title, null, "Announcement is shown in the main area.");
}

function previewAssignment(item) {
  if (!item) return;
  const title = item.name || "Assignment";
  setCourseLocation({ kind: "assignment", id: item.id });
  clearCourseNavActive();
  const meta = [
    formatDate(item.due_at),
    item.points_possible !== null && item.points_possible !== undefined
      ? `${item.points_possible} pts`
      : "",
    Array.isArray(item.submission_types) && item.submission_types.length ? item.submission_types.join(", ") : "",
  ].filter(Boolean).join(" | ");
  const description = item.description || "";
  hideCoursePanels();
  els.courseView.classList.add("detail-open");
  els.courseView.classList.remove("no-right");
  setCourseActionsVisible(false);
  els.panelPageDetail.hidden = false;
  els.pageTitle.textContent = `${state.currentCourse.course_code || state.currentCourse.name || ""} > Assignments > ${title}`;
  els.panelPageDetail.innerHTML = `
    <article class="assignment-preview">
      <h2>${escapeHtml(title)}</h2>
      ${meta ? `<div class="announcement-meta">${escapeHtml(meta)}</div>` : ""}
      <div class="canvas-html-body">${prepareCanvasHtml(description) || "<p>No description archived.</p>"}</div>
      ${renderRubric(item.rubric || [], item.rubric_settings || {})}
    </article>
  `;
  bindCanvasHtmlLinks(els.panelPageDetail, item.linked_files || []);
  showViewer(title, null, "Assignment is shown in the main area.");
}

function previewQuiz(item) {
  if (!item) return;
  const title = item.title || "Quiz";
  setCourseLocation({ kind: "quiz", id: item.id });
  clearCourseNavActive();
  const meta = [
    formatDate(item.due_at),
    item.points_possible !== null && item.points_possible !== undefined ? `${item.points_possible} pts` : "",
    item.question_count ? `${item.question_count} questions` : "",
    item.time_limit ? `${item.time_limit} minutes` : "",
  ].filter(Boolean).join(" | ");
  hideCoursePanels();
  els.courseView.classList.add("detail-open");
  els.courseView.classList.remove("no-right");
  setCourseActionsVisible(false);
  els.panelPageDetail.hidden = false;
  els.pageTitle.textContent = `${state.currentCourse.course_code || state.currentCourse.name || ""} > Quizzes > ${title}`;
  els.panelPageDetail.innerHTML = `
    <article class="assignment-preview">
      <h2>${escapeHtml(title)}</h2>
      ${meta ? `<div class="announcement-meta">${escapeHtml(meta)}</div>` : ""}
      <div class="canvas-html-body">${prepareCanvasHtml(item.description || "") || "<p>No quiz description archived. Quiz attempts and questions are not copied into the local archive.</p>"}</div>
    </article>
  `;
  bindCanvasHtmlLinks(els.panelPageDetail, item.linked_files || []);
  showViewer(title, null, "Quiz metadata is shown in the main area.");
}

function previewDiscussion(item) {
  if (!item) return;
  const title = item.title || "Discussion";
  setCourseLocation({ kind: "discussion", id: item.id });
  clearCourseNavActive();
  const posted = formatDate(item.posted_at || item.delayed_post_at);
  const author = item.user_name ? `<div class="announcement-meta">${escapeHtml(item.user_name)}</div>` : "";
  const date = posted ? `<div class="announcement-meta">${escapeHtml(posted)}</div>` : "";
  hideCoursePanels();
  els.courseView.classList.add("detail-open");
  els.courseView.classList.remove("no-right");
  setCourseActionsVisible(false);
  els.panelPageDetail.hidden = false;
  els.pageTitle.textContent = `${state.currentCourse.course_code || state.currentCourse.name || ""} > Discussions > ${title}`;
  els.panelPageDetail.innerHTML = `
    <article class="announcement-preview">
      <h2>${escapeHtml(title)}</h2>
      ${author}${date}
      <div class="canvas-html-body">${prepareCanvasHtml(item.message || "") || "<p>No discussion body archived.</p>"}</div>
    </article>
  `;
  bindCanvasHtmlLinks(els.panelPageDetail, item.linked_files || []);
  showViewer(title, null, "Discussion prompt is shown in the main area.");
}

function renderRubric(rubric, settings = {}) {
  if (!Array.isArray(rubric) || !rubric.length) return "";
  const title = settings.title || "Rubric";
  return `
    <section class="rubric-panel">
      <h3>${escapeHtml(title)}</h3>
      <div class="rubric-table">
        ${rubric.map(criterion => `
          <div class="rubric-row">
            <div>
              <strong>${escapeHtml(criterion.description || "Criterion")}</strong>
              ${criterion.long_description ? `<p>${escapeHtml(criterion.long_description)}</p>` : ""}
            </div>
            <div>${escapeHtml(formatNumber(criterion.points))} pts</div>
            <div class="rubric-ratings">
              ${(criterion.ratings || []).map(rating => `
                <span><strong>${escapeHtml(formatNumber(rating.points))}</strong> ${escapeHtml(rating.description || "")}</span>
              `).join("")}
            </div>
          </div>
        `).join("")}
      </div>
    </section>
  `;
}

function showViewer(title, openUrl, html) {
  els.viewerHead.hidden = false;
  els.viewerBody.hidden = false;
  els.viewerTitle.textContent = title || "Preview";
  els.viewerBody.className = html === "Select an archived item" ? "viewer-body empty" : "viewer-body";
  els.viewerBody.innerHTML = html || "";
  els.viewerOpen.hidden = !openUrl;
  els.viewerOpen.href = openUrl || "#";
}

function hideViewerPreview() {
  els.viewerHead.hidden = true;
  els.viewerBody.hidden = true;
  els.viewerOpen.hidden = true;
  els.viewerOpen.href = "#";
}

function activateHomePanel() {
  const homeView = inferHomeView();
  if (homeView === "syllabus") return showSyllabusPanel("home");
  if (homeView === "wiki") {
    const page = selectHomePage();
    if (page) return renderArchivedHtmlPanel(page, { activeNav: "home", section: "Home", titleSuffix: "Home" });
  }
  if (homeView === "assignments") return activatePanel("assignments", "home", "Assignments");
  return activatePanel("modules", "home", "Modules");
}

function inferHomeView() {
  const defaultView = state.currentCourse.default_view || "";
  if (defaultView === "syllabus") return "syllabus";
  if (defaultView === "wiki") return "wiki";
  if (defaultView === "assignments") return "assignments";
  if (defaultView === "modules") return "modules";
  if (state.currentCourse.syllabus) return "syllabus";
  if (selectHomePage()) return "wiki";
  if ((state.currentCourse.assignments || []).length && !(state.currentCourse.modules || []).length) return "assignments";
  return "modules";
}

function selectHomePage() {
  if (state.currentCourse.front_page) return state.currentCourse.front_page;
  const pages = state.currentCourse.pages || [];
  return pages.find(page => /home|homepage|quercus homepage/i.test(page.title || "")) || pages[0] || null;
}

function showSyllabusPanel(activeNav = "syllabus") {
  setCourseLocation({ kind: "syllabus", activeNav });
  const syllabus = state.currentCourse.syllabus;
  if (!syllabus?.body) {
    return showEmptyCoursePanel("Syllabus", activeNav, "Syllabus has not been archived yet. Re-run metadata sync for this course.");
  }
  return renderArchivedHtmlPanel(syllabus, {
    activeNav,
    section: "Syllabus",
    titleSuffix: "Syllabus",
    headingText: state.currentCourse.name || state.currentCourse.course_code || "Syllabus",
  });
}

function renderArchivedHtmlPanel(entry, options = {}) {
  const title = entry.title || options.titleSuffix || "Page";
  const section = options.section || "Page";
  hideCoursePanels();
  els.courseView.classList.remove("detail-open");
  els.courseView.classList.remove("no-right");
  setCourseActionsVisible(false);
  setCourseNavActive(options.activeNav || section.toLowerCase());
  els.panelPageDetail.hidden = false;
  els.pageTitle.textContent = `${state.currentCourse.course_code || state.currentCourse.name || state.currentCourse.id} > ${options.titleSuffix || title}`;
  const bodyHtml = prepareCanvasHtml(entry.body || "");
  const headingText = options.headingText || title;
  const showHeading = options.showHeading !== false && !bodyStartsWithTitle(bodyHtml, headingText);
  els.panelPageDetail.innerHTML = `
    <div class="page-detail course-home-page">
      ${showHeading ? `<h2>${escapeHtml(headingText)}</h2>` : ""}
      <div class="canvas-html-body">${bodyHtml || `<p>No archived page body.</p>`}</div>
    </div>
  `;
  bindCanvasHtmlLinks(els.panelPageDetail, entry.linked_files || []);
  hideViewerPreview();
}

function activatePanel(name, activeNav = name, titleOverride = null) {
  setCourseLocation({ kind: "panel", name, activeNav, titleOverride });
  if (name === "files") renderFiles();
  if (name === "pages") renderPages();
  if (name === "announcements") renderAnnouncements();
  if (name === "assignments") renderAssignments();
  if (name === "grades") renderGrades();
  if (name === "quizzes") renderQuizzes();
  if (name === "discussions") renderDiscussions();
  setCourseNavActive(activeNav);
  els.courseView.classList.remove("detail-open");
  if (name === "grades") els.courseView.classList.remove("no-right");
  else els.courseView.classList.add("no-right");
  setCourseActionsVisible(name === "modules");
  els.pageTitle.textContent = `${state.currentCourse.course_code || state.currentCourse.name || state.currentCourse.id} > ${titleOverride || panelTitle(name)}`;
  hideCoursePanels();
  if (name === "modules") els.panelModules.hidden = false;
  if (name === "announcements") els.panelAnnouncements.hidden = false;
  if (name === "files") els.panelFiles.hidden = false;
  if (name === "pages") els.panelPages.hidden = false;
  if (name === "assignments") els.panelAssignments.hidden = false;
  if (name === "grades") els.panelGrades.hidden = false;
  if (name === "quizzes") els.panelQuizzes.hidden = false;
  if (name === "discussions") els.panelDiscussions.hidden = false;
  hideViewerPreview();
}

function showEmptyCoursePanel(label, activeNav = label, message = "No archived items for this section.") {
  setCourseLocation({ kind: "empty", label, activeNav, message });
  setCourseNavActive(activeNav);
  hideCoursePanels();
  els.courseView.classList.remove("detail-open");
  els.courseView.classList.add("no-right");
  setCourseActionsVisible(false);
  els.pageTitle.textContent = `${state.currentCourse.course_code || state.currentCourse.name || state.currentCourse.id} > ${label}`;
  els.panelFiles.hidden = false;
  els.panelFiles.innerHTML = `
    <div class="empty-course-panel">
      <h2>${escapeHtml(label)}</h2>
      <p>${escapeHtml(message)}</p>
    </div>
  `;
  hideViewerPreview();
}

function showGlobalTool(tool) {
  resetCourseNavigation();
  setGlobalActive(tool);
  els.mainArea.classList.remove("course-open");
  els.dashboardView.hidden = true;
  els.coursesView.hidden = true;
  els.globalToolView.hidden = false;
  if (els.utFooter) els.utFooter.hidden = true;
  els.courseView.hidden = true;
  els.emptyView.hidden = false;
  els.emptyView.hidden = true;
  els.backButton.hidden = true;
  setTopDownloadVisible(false);
  const title = globalToolTitle(tool);
  els.pageTitle.textContent = title;
  els.pageSubtitle.textContent = "Local archive";
  els.globalToolView.innerHTML = renderGlobalTool(tool);
  bindGlobalToolLinks(els.globalToolView);
}

function globalToolTitle(tool) {
  return {
    account: "User Settings",
    groups: "Groups",
    calendar: "Calendar",
    inbox: "Inbox",
    history: "Recent History",
    help: "Help",
  }[tool] || "Canvas Tool";
}

function renderGlobalTool(tool) {
  if (tool === "account") return renderAccountTool();
  if (tool === "groups") return renderGroupsTool();
  if (tool === "calendar") return renderCalendarTool();
  if (tool === "inbox") return renderInboxTool();
  if (tool === "history") return renderHistoryTool();
  if (tool === "help") return renderHelpTool();
  return `<div class="tool-panel"><h2>${escapeHtml(globalToolTitle(tool))}</h2><p>No local archive page is defined for this tool yet.</p></div>`;
}

function renderAccountTool() {
  const generated = state.manifest?.generated_at ? new Date(state.manifest.generated_at).toLocaleString() : "Not recorded";
  return `
    <div class="global-two-column">
      <section class="tool-panel profile-panel">
        <div class="profile-avatar">U</div>
        <div>
          <h2>Local User</h2>
          <p>This archive stores course metadata and downloaded files on this computer. Account settings are displayed locally only.</p>
        </div>
      </section>
      <section class="tool-panel">
        <h2>Ways to Contact</h2>
        <div class="settings-row"><strong>Email Addresses</strong><span>Not archived</span></div>
        <div class="settings-row"><strong>Registered Services</strong><span>Local archive only</span></div>
        <div class="settings-row"><strong>Last archive update</strong><span>${escapeHtml(generated)}</span></div>
      </section>
    </div>
  `;
}

function renderGroupsTool() {
  const courses = (state.manifest?.courses || []).slice(0, 10);
  return `
    <section class="tool-panel">
      <h2>Groups</h2>
      <p class="tool-muted">Canvas group membership is not part of the downloaded course documents. The page is kept so the local navigation behaves like Quercus.</p>
      <div class="tool-table">
        <div class="tool-table-header"><span>Group</span><span>Course</span><span>Status</span></div>
        <div class="tool-table-row"><span>No groups archived</span><span>${escapeHtml(courses[0]?.course_code || "")}</span><span>Local placeholder</span></div>
      </div>
    </section>
  `;
}

function renderCalendarTool() {
  const courses = state.manifest?.courses || [];
  return `
    <div class="calendar-layout">
      <section class="tool-panel calendar-main">
        <div class="calendar-toolbar">
          <button type="button">‹</button>
          <button type="button">Today</button>
          <button type="button">›</button>
          <h2>June 2026</h2>
        </div>
        <div class="calendar-weekdays">
          ${["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map(day => `<span>${day}</span>`).join("")}
        </div>
        <div class="calendar-grid-large">
          ${renderCalendarCells()}
        </div>
      </section>
      <aside class="tool-panel calendar-side">
        <h2>Calendars</h2>
        ${courses.slice(0, 12).map(course => `
          <label class="calendar-course">
            <input type="checkbox" checked>
            <span class="course-dot" style="background:${courseColor(course)}"></span>
            <span>${escapeHtml(course.course_code || displayCourseName(course))}</span>
          </label>
        `).join("") || `<p class="tool-muted">No courses archived.</p>`}
        <h2>Undated Events</h2>
        <p class="tool-muted">No undated events archived.</p>
      </aside>
    </div>
  `;
}

function renderCalendarCells() {
  const cells = [];
  for (let i = 31; i <= 35; i += 1) cells.push({ day: i, muted: true });
  for (let day = 1; day <= 30; day += 1) cells.push({ day, today: day === 29 });
  for (let day = 1; day <= 4; day += 1) cells.push({ day, muted: true });
  return cells.map(cell => `
    <div class="calendar-cell${cell.muted ? " muted" : ""}${cell.today ? " today" : ""}">
      <span>${cell.day}</span>
    </div>
  `).join("");
}

function renderInboxTool() {
  return `
    <div class="inbox-layout">
      <section class="tool-panel inbox-list">
        <div class="inbox-toolbar">
          <button type="button">Inbox</button>
          <button type="button">Unread</button>
          <button type="button">Archived</button>
        </div>
        <div class="empty-inbox">No conversations archived</div>
      </section>
      <section class="tool-panel inbox-message">
        <h2>Conversation</h2>
        <p class="tool-muted">Quercus inbox messages are not downloaded by the course archive. Course announcements are available inside each course.</p>
      </section>
    </div>
  `;
}

function renderHistoryTool() {
  const courses = state.manifest?.courses || [];
  return `
    <section class="tool-panel history-panel">
      <h2>Recent History</h2>
      <p class="tool-muted">Local archive history. Click a course to open its archived home page.</p>
      <div class="history-list">
        ${courses.map(course => `
          <button type="button" data-course-id="${escapeHtml(course.id)}">
            <span class="course-dot" style="background:${courseColor(course)}"></span>
            <strong>${escapeHtml(displayCourseName(course))}</strong>
            <small>${escapeHtml(course.term || course.course_code || "")}</small>
          </button>
        `).join("") || `<div class="empty-inbox">No courses archived</div>`}
      </div>
    </section>
  `;
}

function renderHelpTool() {
  return `
    <section class="tool-panel help-panel">
      <h2>Help</h2>
      <button type="button"><span class="tool-icon icon-info"></span> Ask your instructor a question</button>
      <button type="button"><span class="tool-icon icon-info"></span> Search the Canvas Guides</button>
      <button type="button"><span class="tool-icon icon-info"></span> Report a local archive issue</button>
      <button type="button"><span class="tool-icon icon-info"></span> View project README</button>
      <p class="tool-muted">These entries are local UI placeholders. They do not contact Quercus or UofT support.</p>
    </section>
  `;
}

function bindGlobalToolLinks(root) {
  for (const button of root.querySelectorAll("[data-course-id]")) {
    button.addEventListener("click", () => openCourse(button.dataset.courseId));
  }
}

function showCourseUtilityPanel(key, label) {
  if (!state.currentCourse) return;
  setCourseLocation({ kind: "utility", key, label });
  clearCourseNavActive();
  hideCoursePanels();
  els.courseView.classList.remove("detail-open");
  els.courseView.classList.add("no-right");
  setCourseActionsVisible(false);
  els.panelPageDetail.hidden = false;
  els.pageTitle.textContent = `${state.currentCourse.course_code || state.currentCourse.name || state.currentCourse.id} > ${label}`;
  els.panelPageDetail.innerHTML = renderCourseUtility(key, label);
  hideViewerPreview();
}

function renderCourseUtility(key, label) {
  if (key === "stream") {
    return `
      <section class="empty-course-panel utility-panel">
        <h2>${escapeHtml(label)}</h2>
        <div class="stream-item"><strong>Course activity stream</strong><span>Announcements, pages, assignments, and downloaded files are available through the course navigation.</span></div>
        <div class="stream-item"><strong>Local archive status</strong><span>${escapeHtml((state.currentCourse.files || []).filter(file => file.local_path).length)} downloaded files detected.</span></div>
      </section>
    `;
  }
  if (key === "calendar") {
    return `
      <section class="empty-course-panel utility-panel">
        <h2>${escapeHtml(label)}</h2>
        <div class="mini-calendar">${renderMiniCalendar()}</div>
        <p>Calendar events are not separately archived. Assignment due dates are preserved in Assignments when Canvas returned them.</p>
      </section>
    `;
  }
  if (key === "notifications") {
    return `
      <section class="empty-course-panel utility-panel">
        <h2>${escapeHtml(label)}</h2>
        <div class="settings-row"><strong>Announcements</strong><span>Shown inside this course</span></div>
        <div class="settings-row"><strong>Files</strong><span>Opened from local archive when downloaded</span></div>
        <div class="settings-row"><strong>Email notifications</strong><span>Not archived</span></div>
      </section>
    `;
  }
  return `
    <section class="empty-course-panel utility-panel">
      <h2>${escapeHtml(label)}</h2>
      <p>This Canvas utility is preserved as a local page. It does not contain downloadable course documents.</p>
    </section>
  `;
}

function renderMiniCalendar() {
  return `
    <div class="calendar-weekdays">${["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map(day => `<span>${day}</span>`).join("")}</div>
    <div class="calendar-grid-small">${renderCalendarCells()}</div>
  `;
}

function showGlobalPlaceholder(label) {
  resetCourseNavigation();
  setGlobalActive("");
  els.pageTitle.textContent = label;
  els.pageSubtitle.textContent = "Local archive placeholder";
  els.emptyView.innerHTML = `
    <h2>${escapeHtml(label)}</h2>
    <p>This Canvas global tool is shown as a local placeholder. Course documents, pages, announcements, assignments, and downloaded files are archived inside each course.</p>
  `;
}

function setCourseNavActive(navId) {
  for (const button of document.querySelectorAll(".course-link")) {
    button.classList.toggle("active", button.dataset.nav === String(navId));
  }
}

function setCourseActionsVisible(visible) {
  els.courseActions.hidden = !visible;
}

function hideCoursePanels() {
  els.panelModules.hidden = true;
  els.panelAnnouncements.hidden = true;
  els.panelFiles.hidden = true;
  els.panelPages.hidden = true;
  els.panelAssignments.hidden = true;
  els.panelGrades.hidden = true;
  els.panelQuizzes.hidden = true;
  els.panelDiscussions.hidden = true;
  els.panelPageDetail.hidden = true;
}

function resetCourseNavigation() {
  state.currentCourse = null;
  state.currentLocation = null;
  state.courseHistory = [];
  state.restoringLocation = false;
}

function setTopDownloadVisible(visible) {
  if (els.downloadCourseTop) els.downloadCourseTop.hidden = !visible;
}

function setCourseLocation(location) {
  if (!state.currentCourse || !location) return;
  const normalized = JSON.parse(JSON.stringify(location));
  if (
    !state.restoringLocation
    && state.currentLocation
    && JSON.stringify(state.currentLocation) !== JSON.stringify(normalized)
  ) {
    state.courseHistory.push(state.currentLocation);
    if (state.courseHistory.length > 80) state.courseHistory.shift();
  }
  state.currentLocation = normalized;
}

function renderCourseLocation(location) {
  if (!location) return renderCoursesPage();
  state.restoringLocation = true;
  try {
    if (location.kind === "panel") {
      return activatePanel(location.name, location.activeNav, location.titleOverride);
    }
    if (location.kind === "syllabus") {
      return showSyllabusPanel(location.activeNav || "syllabus");
    }
    if (location.kind === "page") {
      const page = findPageByKey(location.key);
      return page ? openPageDetail(page, { activeNav: location.activeNav || "" }) : activateHomePanel();
    }
    if (location.kind === "announcement") {
      const announcement = (state.currentCourse.announcements || [])
        .find(item => String(item.id) === String(location.id));
      return announcement ? previewAnnouncement(announcement) : activatePanel("announcements");
    }
    if (location.kind === "assignment") {
      const assignment = (state.currentCourse.assignments || [])
        .find(item => String(item.id) === String(location.id));
      return assignment ? previewAssignment(assignment) : activatePanel("assignments");
    }
    if (location.kind === "quiz") {
      const quiz = (state.currentCourse.quizzes || [])
        .find(item => String(item.id) === String(location.id));
      return quiz ? previewQuiz(quiz) : activatePanel("quizzes");
    }
    if (location.kind === "discussion") {
      const discussion = (state.currentCourse.discussions || [])
        .find(item => String(item.id) === String(location.id));
      return discussion ? previewDiscussion(discussion) : activatePanel("discussions");
    }
    if (location.kind === "item") {
      return openItemDetail(location.item || {});
    }
    if (location.kind === "empty") {
      return showEmptyCoursePanel(location.label, location.activeNav, location.message);
    }
    if (location.kind === "download") {
      return showDownloadCommandPanel();
    }
    if (location.kind === "utility") {
      return showCourseUtilityPanel(location.key, location.label);
    }
    return activateHomePanel();
  } finally {
    state.restoringLocation = false;
  }
}

function goBack() {
  if (!els.fileOverlay.hidden) {
    closeFileOverlay();
    return;
  }
  if (state.currentCourse && state.courseHistory.length) {
    const previous = state.courseHistory.pop();
    renderCourseLocation(previous);
    return;
  }
  renderCoursesPage();
}

function clearCourseNavActive() {
  for (const button of document.querySelectorAll(".course-link")) {
    button.classList.remove("active");
  }
}

function panelTitle(name) {
  return {
    home: "Home",
    modules: "Modules",
    announcements: "Announcements",
    files: "Files",
    pages: "Pages",
    assignments: "Assignments",
    grades: "Grades",
    quizzes: "Quizzes",
    discussions: "Discussions",
  }[name] || "Modules";
}

function isCurrentCourse(course) {
  const term = String(course.term || "");
  return course.state === "active" || term.includes("2025 Fall") || term.includes("2026");
}

function displayCourseName(course) {
  const name = course.name || course.course_code || `Course ${course.id}`;
  return name === String(course.id) ? "Arrive Ready to Study Mathematics" : name;
}

function courseColor(course) {
  const palette = ["#d17c28", "#cf2f64", "#4d4257", "#2f8f46", "#3997d3", "#2f4e94", "#2f806c", "#6f7a83"];
  return palette[Math.abs(Number(course.id || 0)) % palette.length];
}

function typeIconClass(type) {
  return {
    File: "icon-file",
    Page: "icon-page",
    Assignment: "icon-assignment",
    ExternalUrl: "icon-link",
    ExternalTool: "icon-tool",
    Discussion: "icon-discussion",
    Quiz: "icon-quiz",
    SubHeader: "icon-subheader",
  }[type] || "icon-page";
}

function dedupeLinks(items) {
  const seen = new Set();
  const result = [];
  for (const item of items) {
    const key = `${item.label}|${item.html_url}`;
    if (!seen.has(key)) {
      seen.add(key);
      result.push(item);
    }
  }
  return result;
}

function setGlobalActive(name) {
  for (const button of document.querySelectorAll(".nav-icon[data-global], .nav-icon[data-global-tool]")) {
    button.classList.toggle("active", button.dataset.global === name || button.dataset.globalTool === name);
  }
}

function formatDate(value) {
  return value ? new Date(value).toLocaleString() : "";
}

function formatNumber(value) {
  if (value === null || value === undefined || value === "") return "";
  const number = Number(value);
  if (!Number.isFinite(number)) return String(value);
  return Number.isInteger(number) ? String(number) : number.toFixed(2).replace(/0+$/, "").replace(/\.$/, "");
}

function formatGradePercent(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "-";
  return `${formatNumber(number)}%`;
}

function formatPoints(earned, possible) {
  if (earned === null || earned === undefined || possible === null || possible === undefined) return "-";
  return `${formatNumber(earned)} / ${formatNumber(possible)}`;
}

function classifyExternalKind(title = "", url = "", type = "") {
  const value = `${title} ${url} ${type}`.toLowerCase();
  if (/youtube|youtu\.be|vimeo|panopto|kaltura|mediasite|screenpal|h5p|lecture|video|zoom/.test(value)) {
    return "video";
  }
  if (/piazza|markus|gradescope|wileyplus|mathmatize|connect\.mheducation|externaltool/.test(value)) {
    return "tool";
  }
  if (/mailto:/.test(value)) return "email";
  if (isCanvasUrl(url) || /\/courses\/\d+/.test(value) || /\/api\/v1\/courses\/\d+/.test(value)) {
    return "canvas";
  }
  return "link";
}

function externalKindLabel(kind) {
  return {
    video: "External video or interactive content",
    tool: "External course tool",
    email: "Email link",
    canvas: "Canvas link",
    link: "External link",
  }[kind] || "External link";
}

function iconClassForExternalKind(kind) {
  return {
    video: "icon-video",
    tool: "icon-tool",
    email: "icon-mail",
    canvas: "icon-page",
    link: "icon-link",
  }[kind] || "icon-link";
}

function absoluteCanvasUrl(url) {
  const value = String(url || "");
  if (!value) return "";
  if (/^(https?:|mailto:)/i.test(value)) return value;
  if (value.startsWith("//")) return `https:${value}`;
  if (value.startsWith("/")) {
    const baseUrl = canvasBaseUrl();
    return `${baseUrl.replace(/\/$/, "")}${value}`;
  }
  return value;
}

function openExternal(url) {
  if (url) window.open(url, "_blank", "noreferrer");
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

els.backButton.addEventListener("click", goBack);
document.querySelector('[data-global="dashboard"]').addEventListener("click", renderDashboard);
for (const button of document.querySelectorAll('[data-global="courses"]')) {
  button.addEventListener("click", renderCoursesPage);
}
if (els.dashboardSearch) {
  els.dashboardSearch.addEventListener("input", () => {
    state.dashboardQuery = els.dashboardSearch.value;
    renderDashboard();
  });
}
for (const button of document.querySelectorAll(".nav-icon[data-global-tool]")) {
  button.addEventListener("click", () => showGlobalTool(button.dataset.globalTool));
}
for (const button of document.querySelectorAll(".course-tool-list button")) {
  button.addEventListener("click", () => {
    if (!state.currentCourse) return;
    const label = button.textContent.trim();
    showCourseUtilityPanel(button.dataset.courseUtility || "", label);
  });
}
els.collapseButton.addEventListener("click", () => {
  state.collapsed = !state.collapsed;
  for (const list of document.querySelectorAll(".module-items")) {
    list.hidden = state.collapsed;
  }
  els.collapseButton.textContent = state.collapsed ? "Expand All" : "Collapse All";
});
els.fileOverlayClose.addEventListener("click", () => {
  closeFileOverlay();
});

for (const button of document.querySelectorAll(".course-link[data-panel]")) {
  button.addEventListener("click", () => activatePanel(button.dataset.panel));
}

for (const button of document.querySelectorAll(".course-link[data-empty]")) {
  button.addEventListener("click", () => showEmptyCoursePanel(button.dataset.empty));
}

loadManifest();
