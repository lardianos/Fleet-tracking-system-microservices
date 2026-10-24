export interface AuditChange {
    from_value: unknown;
    to_value: unknown;
}

export interface AuditLog {
    id: string;
    timestamp: string;
    entity_type: string;
    entity_id: string;
    action: string;
    description: string;
    performed_by: string | null;
    related_entities: Record<string, string | null>;
    changes: Record<string, AuditChange>;
}

export interface AuditLogPage {
    logs: AuditLog[];
    has_more: boolean;
    next_cursor: {
        before_time: string;
        before_id: string;
    } | null;
    end_time: string;
}