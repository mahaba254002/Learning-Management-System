import { useTeachingQuery } from '../teacher/teachingQueries';
import { PageHeading } from '../teacher/TeachingUI';
import { ProgressionHistory } from '../institution/StudentProgressionPage';
export default function StudentProgressionPage(){const query=useTeachingQuery('/api/student/progression');return <><PageHeading title="My progression">Your institution-approved advancement, repeat and completion decisions.</PageHeading><ProgressionHistory query={query}/></>;}
