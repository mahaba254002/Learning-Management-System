import { useState, forwardRef } from "react";
import "./PasswordInput.css";
import MaterialIcon from './MaterialIcon';

/**
 * A password <input> with a show/hide toggle. Built with forwardRef so
 * React Hook Form's register() can still attach its ref correctly — this
 * is required for RHF to read the input's value, since register() returns
 * a ref along with onChange/onBlur/name.
 */
const PasswordInput = forwardRef(function PasswordInput(props, ref) {
  const [visible, setVisible] = useState(false);

  return (
    <div className="password-input">
      <input
        {...props}
        ref={ref}
        type={visible ? "text" : "password"}
      />
      <button
        type="button"
        className="password-input__toggle"
        onClick={() => setVisible((v) => !v)}
        aria-label={visible ? "Hide password" : "Show password"}
        aria-pressed={visible}
      >
        <MaterialIcon name={visible ? 'visibility_off' : 'visibility'} />
      </button>
    </div>
  );
});

export default PasswordInput;
