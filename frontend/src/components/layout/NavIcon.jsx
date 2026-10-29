const paths = {
  dashboard: "M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h7v7h-7z",
  institutions: "M4 21V7l8-4 8 4v14M2 21h20M8 9h1m6 0h1M8 13h1m6 0h1M10 21v-4h4v4",
  users: "M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M16 3a4 4 0 0 1 0 8M22 21v-2a4 4 0 0 0-3-3.87M13 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0",
  billing: "M3 5h18v14H3zM3 9h18M7 15h4",
  backup: "M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5",
  restore: "M3 11a9 9 0 1 1 2 7M3 4v7h7M12 7v5l3 2",
  audit: "M8 3h8l3 3v15H5V3h3M8 9h8M8 13h8M8 17h5",
  settings: "M12 8a4 4 0 1 1 0 8 4 4 0 0 1 0-8M9 3h6l1 3 3 1 2 5-2 5-3 1-1 3H9l-1-3-3-1-2-5 2-5 3-1z",
  usage: "M4 20V10m8 10V4m8 16v-8M2 21h20",
  menu: "M4 5h16v14H4zM9 5v14",
  'collapse-sidebar': 'M14 6l-6 6 6 6',
  'expand-sidebar': 'M10 6l6 6-6 6',
  logout: "M9 4H4v16h5M9 12h12m-4-4 4 4-4 4",
  'academic-years': 'M4 5h16v16H4zM8 2v6m8-6v6M4 10h16M8 14h2m4 0h2M8 18h2',
  'academic-structure': 'M9 3h6v5H9zM3 16h6v5H3zM15 16h6v5h-6zM12 8v4M6 16v-4h12v4',
  'course-enrollment': 'M3 5h10v16H3zM7 9h2m-2 4h2m7-7 2 2 4-4m-6 11 2 2 4-4',
  'student-imports': 'M5 3h10l4 4v14H5zM14 3v5h5M8 14h8m-4-4v8m-3-3 3 3 3-3',
  classes: 'M3 3h18v14H3zM8 21h8m-4-4v4M7 7h10m-10 4h5',
  subjects: 'M3 4h6l3 3 3-3h6v16h-6l-3 2-3-2H3zM12 7v15',
  attendance: 'M5 3h14v18H5zM8 8h8m-8 4h3m-3 4 2 2 5-5',
  coursework: 'M6 3h9l4 4v14H6zM14 3v5h5M9 12h7m-7 4h5',
  reports: 'M5 3h14v18H5zM8 7h8m-8 4h8m-8 4h5M15 18l2 2 4-4',
  'academic-record': 'M5 3h14v18H5zM8 7h8m-8 4h8m-8 4h5',
};
export default function NavIcon({ name }) {
  return <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={paths[name] || paths.users} /></svg>;
}
