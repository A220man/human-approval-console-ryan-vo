export interface UserProfile {
  user_id: string;
  username: string;
  email: string;
  roles: string[];
}

export interface PolicyViolation {
  policy_id: string;
  policy_name: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  required_role: string;
  auto_reject: boolean;
  matched_detail: string;
}

export interface ActionItem {
  id: string;
  agent_id: string;
  agent_framework: string;
  session_id: string;
  action_type: 'shell_command' | 'file_mutation' | 'database_query' | 'api_call' | 'privilege_escalation' | 'financial_transaction';
  target_resource: string;
  payload: Record<string, unknown>;
  intent: string;
  context_metadata?: Record<string, unknown>;
  risk_score: number;
  risk_level: 'low' | 'medium' | 'high' | 'critical';
  status: 'pending' | 'under_review' | 'approved' | 'rejected' | 'modified_and_approved' | 'expired';
  reviewer_id?: string;
  reviewer_role?: string;
  reviewed_at?: string;
  rationale?: string;
  modified_payload?: Record<string, unknown>;
  created_at: string;
  expires_at?: string;
  violations?: PolicyViolation[];
  receipt_id?: string;
}

export interface QueueStats {
  pending: number;
  under_review: number;
  approved: number;
  rejected: number;
  critical_pending: number;
}

export interface ActionListResponse {
  total: number;
  limit: number;
  offset: number;
  stats: QueueStats;
  items: ActionItem[];
}

export interface ReceiptItem {
  id: string;
  action_id: string;
  agent_id: string;
  decision: string;
  reviewer_id: string;
  reviewer_role: string;
  signed_at: string;
  payload_hash: string;
  rationale_hash: string;
  receipt_hash: string;
  prev_receipt_hash: string;
  signature: string;
  receipt_data: Record<string, unknown>;
}

export interface ReceiptVerifyResult {
  receipt_id: string;
  is_valid: boolean;
  signature_valid: boolean;
  payload_hash_matches: boolean;
  rationale_hash_matches: boolean;
  chain_link_intact: boolean;
  details: string;
}

export interface ChainVerifyResult {
  is_valid: boolean;
  total_receipts: number;
  verified_count: number;
  genesis_hash: string;
  head_receipt_hash?: string | null;
  broken_at_receipt_id?: string | null;
  details: string;
}

export interface AdvisoryResponse {
  action_id: string;
  provider: string;
  model: string;
  is_advisory: boolean;
  summary: string;
  blast_radius_assessment: string;
  security_concerns: string[];
  suggested_modifications?: string;
  offline_deterministic: boolean;
}

export interface PolicyItem {
  id: string;
  name: string;
  description: string;
  action_type: string;
  rule_pattern: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  required_role: 'viewer' | 'analyst' | 'admin';
  auto_reject: boolean;
  enabled: boolean;
  created_at: string;
}

export interface BenchmarkAction {
  id: string;
  action_type: string;
  target_resource: string;
  payload: Record<string, unknown>;
  intent: string;
  ground_truth_destructive: boolean;
  ground_truth_risk_level: string;
  expected_rejection: boolean;
  category: string;
}

export interface EvaluationMetrics {
  total_samples: number;
  destructive_samples: number;
  benign_samples: number;
  true_positives: number;
  false_positives: number;
  true_negatives: number;
  false_negatives: number;
  precision: number;
  recall: number;
  f1_score: number;
  accuracy: number;
  critical_false_negative_rate: number;
  confusion_matrix: {
    true_positives: number;
    false_positives: number;
    true_negatives: number;
    false_negatives: number;
  };
  breakdown_by_category: Record<string, {
    total: number;
    accuracy: number;
    false_negatives: number;
  }>;
}
