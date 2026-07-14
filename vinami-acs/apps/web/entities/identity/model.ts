export interface IdentityView {
  actorId: string;
  displayName: string;
  primaryRole: string;
  roles: string[];
  permissions: string[];
  provider: string;
  mode: string;
  developmentOnly: boolean;
  expiresAt: string;
}
