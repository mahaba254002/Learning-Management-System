import test from 'node:test';
import assert from 'node:assert/strict';
import { changeModule, navItemVisible, pageEnabled } from '../src/modules/institutionModules.js';

const dependencies = { course_allocation: ['staff_directory'], student_records: ['course_allocation'], student_portal: ['student_records'], coursework: ['student_records'], assessments: ['coursework'], academic_reports: ['assessments'], staff_attendance: ['staff_directory'] };
const management = { staff_directory: true, course_allocation: true, staff_attendance: true, student_records: false, student_portal: false, student_attendance: false, coursework: false, assessments: false, academic_reports: false, learning_materials: false, progression: false };

test('management package keeps operations available and hides student learning', () => {
  for (const path of ['/institution/staff', '/institution/departments', '/institution/allocations', '/institution/staff-attendance', '/teacher/allocations']) assert.equal(pageEnabled(path, management), true, path);
  for (const path of ['/institution/coursework', '/institution/students', '/institution/reports', '/teacher/materials', '/teacher/scores', '/student/dashboard', '/student/profile']) assert.equal(pageEnabled(path, management), false, path);
});

test('student records can be enabled while student portal remains disabled', () => {
  const modules = { ...management, student_records: true, student_attendance: true };
  assert.equal(pageEnabled('/institution/classes/abc', modules), true);
  assert.equal(pageEnabled('/institution/attendance', modules), true);
  assert.equal(pageEnabled('/student/attendance', modules), false);
});

test('enabling a dependent feature enables its prerequisites without unrelated features', () => {
  const modules = changeModule(management, 'academic_reports', true, dependencies);
  assert.equal(modules.student_records, true);
  assert.equal(modules.coursework, true);
  assert.equal(modules.assessments, true);
  assert.equal(modules.student_portal, false);
  assert.equal(modules.learning_materials, false);
  assert.equal(management.academic_reports, false);
});

test('disabling a prerequisite cascades to all dependent features', () => {
  const modules = changeModule({ ...management, student_records: true, student_portal: true, coursework: true, assessments: true, academic_reports: true }, 'student_records', false, dependencies);
  assert.equal(modules.student_portal, false);
  assert.equal(modules.coursework, false);
  assert.equal(modules.assessments, false);
  assert.equal(modules.academic_reports, false);
  assert.equal(modules.staff_attendance, true);
});

test('account and package controls remain available when every optional module is off', () => {
  const modules = Object.fromEntries(Object.keys(management).map(key => [key, false]));
  assert.equal(pageEnabled('/institution/account', modules), true);
  assert.equal(pageEnabled('/institution/modules', modules), true);
  assert.equal(pageEnabled('/institution/dashboard', undefined), false);
});

test('sidebar keeps module-free pages while modules are loading or unavailable', () => {
  assert.equal(navItemVisible('/institution/dashboard', undefined), true);
  assert.equal(navItemVisible('/institution/account', undefined), true);
  assert.equal(navItemVisible('/student/dashboard', undefined), true);
  assert.equal(navItemVisible('/institution/students', undefined), false);
  assert.equal(navItemVisible('/student/assignments', undefined), false);
  assert.equal(navItemVisible('/institution/students', { student_records: true }), true);
});
