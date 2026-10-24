import { Fragment, useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import type { AuditLog, AuditLogPage } from "../types/AuditLog";
import { authenticatedFetch } from "../auth/session";

function displayAuditValue(value: unknown): string {
    // Διατηρούμε τη διάκριση ανάμεσα σε null, κενό string και άλλες τιμές.
    if (value === undefined) return "—";

    const text = JSON.stringify(value);

    if (typeof text === "string") return text;

    return String(value);
}

function displayAuditTime(value: string): string {
    // Οι παλιές εγγραφές χωρίς timezone έχουν αποθηκευτεί ως UTC.
    let timestamp = value;

    if (!/(Z|[+-]\d{2}:\d{2})$/i.test(timestamp)) {
        timestamp += "Z";
    }

    return new Date(timestamp).toLocaleString();
}

function AuditLogs() {
    const [entityType, setEntityType] = useState("");
    const [entityId, setEntityId] = useState("");
    const [action, setAction] = useState("");
    const [startTime, setStartTime] = useState("");
    const [endTime, setEndTime] = useState("");

    const [logs, setLogs] = useState<AuditLog[]>([]);
    const [selectedAuditId, setSelectedAuditId] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState(false);
    const [hasSearched, setHasSearched] = useState(false);
    const [hasMore, setHasMore] = useState(false);
    const [error, setError] = useState("");

    const requestController = useRef<AbortController | null>(null);
    const nextPageQuery = useRef<URLSearchParams | null>(null);

    useEffect(() => {
        return () => {
            // Ακυρώνουμε την ανάκτηση όταν κλείνει η ενότητα.
            if (requestController.current !== null) {
                requestController.current.abort();
            }
        };
    }, []);

    function toggleAuditDetails(auditId: string) {
        if (selectedAuditId === auditId) {
            setSelectedAuditId(null);
        } else {
            setSelectedAuditId(auditId);
        }
    }

    async function loadAuditLogs(loadNextPage: boolean) {
        if (requestController.current !== null) return;

        let params: URLSearchParams;

        if (loadNextPage) {
            if (nextPageQuery.current === null) return;

            // Χρησιμοποιούμε τα φίλτρα της προηγούμενης αναζήτησης.
            params = new URLSearchParams(nextPageQuery.current);
        } else {
            params = new URLSearchParams({ limit: "50" });

            if (entityType !== "") params.set("entity_type", entityType);
            if (entityId.trim() !== "") params.set("entity_id", entityId.trim());
            if (action !== "") params.set("action", action);

            let start: Date | null = null;
            let end: Date | null = null;

            if (startTime !== "") start = new Date(startTime);
            if (endTime !== "") end = new Date(endTime);

            if (start !== null && !Number.isFinite(start.getTime())) {
                setError("Select a valid start time.");
                return;
            }

            if (end !== null && !Number.isFinite(end.getTime())) {
                setError("Select a valid end time.");
                return;
            }

            if (start !== null && end !== null && start >= end) {
                setError("Start time must be earlier than end time.");
                return;
            }

            if (start !== null) params.set("start_time", start.toISOString());
            if (end !== null) params.set("end_time", end.toISOString());

            setLogs([]);
            setSelectedAuditId(null);
            setHasMore(false);
            setHasSearched(false);
            nextPageQuery.current = null;
        }

        const controller = new AbortController();
        requestController.current = controller;

        setIsLoading(true);
        setError("");

        try {
            const response = await authenticatedFetch(
                `http://localhost:8004/api/v1/admin/audit-logs?${params.toString()}`,
                { signal: controller.signal }
            );

            if (!response.ok) {
                let message = `Could not retrieve audit logs: ${response.status}`;
                const body = await response.json().catch(() => null);

                if (body !== null && typeof body.detail === "string") {
                    message = body.detail;
                }

                throw new Error(message);
            }

            const result: AuditLogPage = await response.json();

            if (controller.signal.aborted) return;

            // Ελέγχουμε τη σελιδοποίηση πριν ενημερώσουμε τα αποτελέσματα.
            if (result.has_more && result.next_cursor === null) {
                throw new Error("The audit response is missing its next-page cursor.");
            }

            setLogs((previous) => {
                if (!loadNextPage) return result.logs;

                return [...previous, ...result.logs];
            });

            setHasSearched(true);
            setHasMore(result.has_more);

            nextPageQuery.current = null;

            if (result.has_more && result.next_cursor !== null) {
                const nextParams = new URLSearchParams(params);

                // Κρατάμε σταθερό χρονικό παράθυρο για την ίδια αναζήτηση.
                nextParams.set("end_time", result.end_time);
                nextParams.set("before_time", result.next_cursor.before_time);
                nextParams.set("before_id", result.next_cursor.before_id);

                nextPageQuery.current = nextParams;
            }
        } catch (requestError) {
            if (controller.signal.aborted) return;

            let message = "Could not retrieve audit logs.";

            if (requestError instanceof Error) {
                message = requestError.message;
            }

            setError(message);
        } finally {
            if (requestController.current === controller) {
                requestController.current = null;

                if (!controller.signal.aborted) {
                    setIsLoading(false);
                }
            }
        }
    }

    function searchAuditLogs(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();
        void loadAuditLogs(false);
    }

    let searchButtonText = "Search";

    if (isLoading) searchButtonText = "Loading...";

    return (
        <section>
            <h3>Audit Logs</h3>
            <p>Business changes, newest first. Times use your browser timezone.</p>

            <form onSubmit={searchAuditLogs}>
                <div>
                    <label htmlFor="audit-entity-type">Entity Type</label>
                    <select id="audit-entity-type" value={entityType} onChange={(event) => setEntityType(event.target.value)} disabled={isLoading}>
                        <option value="">All</option>
                        <option value="FLEET">Fleet</option>
                        <option value="FLEET_MANAGER">Fleet Manager</option>
                        <option value="DRIVER">Driver</option>
                        <option value="VEHICLE">Vehicle</option>
                    </select>
                </div>

                <div>
                    <label htmlFor="audit-entity-id">Entity ID</label>
                    <input id="audit-entity-id" value={entityId} onChange={(event) => setEntityId(event.target.value)} disabled={isLoading}/>
                </div>

                <div>
                    <label htmlFor="audit-action">Action</label>
                    <select id="audit-action" value={action} onChange={(event) => setAction(event.target.value)} disabled={isLoading}>
                        <option value="">All</option>
                        <option value="CREATED">Created</option>
                        <option value="UPDATED">Updated</option>
                        <option value="ACTIVATED">Activated</option>
                        <option value="DEACTIVATED">Deactivated</option>
                        <option value="DELETED">Deleted</option>
                        <option value="DRIVER_UNASSIGNED">Driver unassigned</option>
                    </select>
                </div>

                <div>
                    <label htmlFor="audit-from">From</label>
                    <input id="audit-from" type="datetime-local" value={startTime} onChange={(event) => setStartTime(event.target.value)} disabled={isLoading}/>
                </div>

                <div>
                    <label htmlFor="audit-to">To</label>
                    <input id="audit-to" type="datetime-local" value={endTime} onChange={(event) => setEndTime(event.target.value)} disabled={isLoading}/>
                </div>

                <button type="submit" disabled={isLoading}> {searchButtonText} </button>
            </form>

            {error !== "" && (<p role="alert">{error}</p>)}
            {hasSearched && (<p>Loaded audit records: {logs.length}</p>)}
            {hasSearched && logs.length === 0 && (<p>No audit records match these filters.</p>)}

            {logs.length > 0 && (
                <div className="audit-logs-table">
                    <table>
                        <thead>
                            <tr>
                                <th>Time</th>
                                <th>Entity</th>
                                <th>Entity ID</th>
                                <th>Action</th>
                                <th>Description</th>
                                <th>Details</th>
                            </tr>
                        </thead>

                        <tbody>
                            {logs.map((audit) => (
                                <Fragment key={audit.id}>
                                    <tr>
                                        <td>{displayAuditTime(audit.timestamp)}</td>
                                        <td>{audit.entity_type}</td>
                                        <td>{audit.entity_id}</td>
                                        <td>{audit.action}</td>
                                        <td>{audit.description}</td>
                                        <td>
                                            <button type="button" aria-expanded={selectedAuditId === audit.id} onClick={() => toggleAuditDetails(audit.id)}> View </button>
                                        </td>
                                    </tr>

                                    {selectedAuditId === audit.id && (
                                        <tr>
                                            <td colSpan={6}>
                                                <div className="audit-log-details">
                                                    <p>Audit ID: {audit.id}</p>
                                                    <p>Performed by: {audit.performed_by || "—"}</p>

                                                    <h4>Related Entities</h4>

                                                    {Object.entries(audit.related_entities).map(([name, value]) => (
                                                        <p key={name}>{name}: {displayAuditValue(value)}</p>
                                                    ))}

                                                    <h4>Changes</h4>

                                                    {Object.keys(audit.changes).length === 0 && (<p>No field changes recorded.</p>)}

                                                    {Object.entries(audit.changes).map(([field, change]) => (
                                                        <div className="audit-log-change" key={field}>
                                                            <strong>{field}</strong>
                                                            <p>Previous: <code>{displayAuditValue(change.from_value)}</code></p>
                                                            <p>New: <code>{displayAuditValue(change.to_value)}</code></p>
                                                        </div>
                                                    ))}
                                                </div>
                                            </td>
                                        </tr>
                                    )}
                                </Fragment>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}

            {hasMore && (
                <button type="button" onClick={() => void loadAuditLogs(true)} disabled={isLoading}> Load more </button>
            )}
        </section>
    );
}

export default AuditLogs;