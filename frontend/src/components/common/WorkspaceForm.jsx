import { useAuth } from "../../context/useAuth";

export default function WorkspaceForm({ children, ...props }) {
  const { readOnly } = useAuth();
  return <form {...props}><fieldset className="workspace-form-fields" disabled={readOnly}>{children}</fieldset></form>;
}
