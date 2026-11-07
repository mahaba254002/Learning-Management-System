export const moduleLabels = {
  staff_directory: ['Staff directory', 'Teaching and non-teaching employees, departments and employment records.'],
  course_allocation: ['Course allocation', 'Course catalogue, academic calendar and staff workloads.'],
  staff_attendance: ['Staff attendance', 'Daily registers for teaching and non-teaching staff.'],
  student_records: ['Student records', 'Admissions, groups, enrollment and student administration.'],
  student_attendance: ['Student attendance', 'Class and course attendance registers.'],
  student_portal: ['Student portal', 'Allow student sign-in and access to enabled student features.'],
  learning_materials: ['Learning materials', 'Publish resources and course content.'],
  coursework: ['Coursework and submissions', 'Prepare assignments and review student submissions.'],
  assessments: ['Marks and outcomes', 'Record marks, competencies and approved course outcomes.'],
  academic_reports: ['Academic reports', 'Report cards, transcripts and class reports.'],
  progression: ['Student progression', 'Progression decisions and academic year promotions.'],
};

export const presetLabels = { MANAGEMENT: 'Management Only', MANAGEMENT_WITH_STUDENTS: 'Management + Student Records', FULL: 'Management + Learning' };

export function changeModule(current, key, enabled, dependencies) {
  const next = { ...current, [key]: enabled };
  function enable(feature) { next[feature] = true; (dependencies[feature] || []).forEach(enable); }
  if (enabled) enable(key);
  else {
    let changed = true;
    while (changed) {
      changed = false;
      for (const [feature, parents] of Object.entries(dependencies)) {
        if (next[feature] && parents.some(parent => !next[parent])) { next[feature] = false; changed = true; }
      }
    }
  }
  return next;
}

export function pageModules(path) {
  const section = path.split('/')[2];
  const required = {
    staff: ['staff_directory'], departments: ['staff_directory'], allocations: ['course_allocation'], 'staff-attendance': ['staff_attendance'],
    invitations: ['staff_directory'], teachers: ['staff_directory'],
    classes: ['student_records'], 'academic-structure': ['course_allocation'], 'academic-years': ['course_allocation'],
    'course-enrollment': ['student_records'], students: ['student_records'], 'student-imports': ['student_records'],
    'student-records': ['student_records'], fees: ['student_records'], timetable: ['course_allocation'], marks: ['assessments'], messages: ['student_records'],
    attendance: ['student_attendance'], materials: ['learning_materials'], coursework: ['coursework'],
    assignments: ['coursework'], scores: ['assessments'], grades: ['assessments'],
    reports: ['academic_reports'], progression: ['progression'], 'academic-record': ['assessments'],
    subjects: ['course_allocation'],
  }[section] || [];
  return path.startsWith('/student/') ? ['student_portal', ...required] : required;
}

export function pageEnabled(path, modules) {
  return Boolean(modules) && pageModules(path).every(key => modules[key]);
}

// The sidebar must never go empty while modules load or if that request fails.
// Until modules are known it shows pages that need no module (dashboard,
// account, audit). Signed-in students already passed the student portal check.
export function navItemVisible(path, modules) {
  if (modules) return pageEnabled(path, modules);
  return pageModules(path).every(key => key === 'student_portal');
}
