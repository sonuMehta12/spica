/**
 * The slice of Google Identity Services this app uses.
 *
 * Hand-written rather than pulled from `@types/google.accounts`: three calls
 * are used and a dependency for them would be larger than the declaration.
 */
interface GoogleIdConfig {
  client_id: string;
  callback: (response: { credential?: string; select_by?: string }) => void;
  use_fedcm_for_prompt?: boolean;
  auto_select?: boolean;
}

interface GoogleButtonOptions {
  theme?: 'outline' | 'filled_blue' | 'filled_black';
  size?: 'small' | 'medium' | 'large';
  shape?: 'rectangular' | 'pill' | 'circle' | 'square';
  text?: 'signin_with' | 'signup_with' | 'continue_with' | 'signin';
  width?: number;
  logo_alignment?: 'left' | 'center';
}

interface Window {
  google?: {
    accounts?: {
      id: {
        initialize: (config: GoogleIdConfig) => void;
        renderButton: (parent: HTMLElement, options: GoogleButtonOptions) => void;
        disableAutoSelect: () => void;
      };
    };
  };
}
