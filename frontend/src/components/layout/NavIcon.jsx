import MaterialIcon from '../common/MaterialIcon';

const symbols = {
  dashboard: 'dashboard', institutions: 'domain', users: 'group', billing: 'payments',
  backup: 'backup', restore: 'history', audit: 'history', settings: 'settings', usage: 'monitoring',
  menu: 'menu', 'collapse-sidebar': 'chevron_left', 'expand-sidebar': 'chevron_right', logout: 'logout',
  'academic-years': 'calendar_month', 'academic-structure': 'account_tree', 'course-enrollment': 'how_to_reg',
  'student-imports': 'upload_file', classes: 'school', subjects: 'menu_book', attendance: 'fact_check',
  coursework: 'assignment', reports: 'description', 'academic-record': 'school',
  teachers: 'person', students: 'school', profile: 'person', account: 'person', invitations: 'person_add',
  materials: 'folder_open', scores: 'grading', grades: 'grading', progression: 'school',
  staff: 'badge', departments: 'corporate_fare', allocations: 'assignment', 'staff-attendance': 'event_available',
  modules: 'settings',
  // Closest symbols in the bundled set for the newer pages.
  timetable: 'calendar_month', courses: 'cast_for_education', registration: 'how_to_reg', 'course-registration': 'how_to_reg',
  assignments: 'assignment', announcements: 'description', messages: 'group', requests: 'assignment', storage: 'folder_open',
  messaging: 'monitoring', 'grading-requests': 'grading', grading: 'grading', marks: 'grading', fees: 'payments',
  'student-records': 'school', payments: 'payments', 'platform-users': 'group',
};

export default function NavIcon({ name }) {
  return <MaterialIcon name={symbols[name] || 'group'} />;
}
