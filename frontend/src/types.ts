export interface Person {
  id: number;
  name: string;
  avatar_key: string;
  group_count?: number;
}
export interface Group {
  id: number;
  name: string;
  member_count: number;
  expense_count: number;
  total_expense_minor: number;
  member_preview: Person[];
}
export interface Workspace {
  id: number;
  scope: "workspace" | "group";
  group_id: number | null;
  can_switch_to_owner: boolean;
}
export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}
export interface Expense {
  id: number;
  group_id: number;
  description: string;
  paid_by: Person;
  amount_minor: number;
  created_at: string;
  participant_count: number;
  split_type?: "equal" | "custom";
  receipt_url?: string | null;
  has_receipt?: boolean;
  shares: {
    user_id: number;
    name: string;
    avatar_key: string;
    amount_minor: number;
  }[];
}
export interface Debt {
  from_user_id: number;
  to_user_id: number;
  amount_minor: number;
  amount: string;
}
export interface BalanceMember {
  user_id: number;
  name: string;
  avatar_key: string;
  paid_minor: number;
  allocated_minor: number;
  owes_minor: number;
  receivable_minor: number;
  net_minor: number;
}
export interface Balances {
  debts: Debt[];
  members: BalanceMember[];
}
export interface Explanation {
  amount_minor: number;
  from_user_id: number | null;
  to_user_id: number | null;
  signed_total_minor: number;
  items: {
    type: string;
    record_id: number;
    description: string;
    created_at: string;
    contribution_minor: number;
  }[];
  total: number;
}
