/** @odoo-module **/

/**
 * Pure, framework-free helpers that turn the per-column filter conditions
 * collected in the popover into Odoo domains, and produce the human-readable
 * facet label shown in the search bar.
 *
 * This file is intentionally UI-free so it can be reused as-is across the
 * 17.0 / 18.0 / 19.0 branches and unit-tested in isolation.
 *
 * A "condition" is a plain object: { operator, value, value2 }
 *   - value2 is only used by range operators ("between", date ranges).
 * Conditions on the SAME column are OR'd together; different columns are AND'd
 * by the search model when each column is pushed as its own facet.
 */

// Which raw field types we render a filter widget for.
export const SUPPORTED_FIELD_TYPES = [
    "char",
    "text",
    "html",
    "integer",
    "float",
    "monetary",
    "date",
    "datetime",
    "boolean",
    "selection",
    "many2one",
    "many2many",
    "one2many",
];

export const TEXT_OPERATORS = [
    { op: "ilike", label: "contains" },
    { op: "not ilike", label: "does not contain" },
    { op: "=", label: "is equal to" },
    { op: "!=", label: "is not equal to" },
    { op: "=like_start", label: "starts with" },
];

export const NUMERIC_OPERATORS = [
    { op: "=", label: "=" },
    { op: "!=", label: "≠" },
    { op: ">", label: ">" },
    { op: "<", label: "<" },
    { op: ">=", label: "≥" },
    { op: "<=", label: "≤" },
    { op: "between", label: "between" },
];

/**
 * Map an Odoo field type to the widget "kind" the popover renders.
 * @param {Object} field a field definition ({ type, relation, ... })
 * @returns {string}
 */
export function widgetKindForField(field) {
    switch (field.type) {
        case "char":
        case "text":
        case "html":
            return "text";
        case "integer":
        case "float":
        case "monetary":
            return "numeric";
        case "date":
        case "datetime":
            return "date";
        case "boolean":
            return "boolean";
        case "selection":
            return "selection";
        case "many2one":
            return "many2one";
        case "many2many":
        case "one2many":
            return "many2many";
        default:
            return null;
    }
}

/** Default (empty) condition for a given widget kind. */
export function defaultCondition(kind, field) {
    switch (kind) {
        case "text":
            return { operator: "ilike", value: "" };
        case "numeric":
            return { operator: "=", value: "", value2: "" };
        case "date":
            return { operator: "between", value: "", value2: "" };
        case "boolean":
            return { operator: "=", value: true };
        case "selection":
            return { operator: "in", value: [] };
        case "many2one":
        case "many2many":
            return { operator: "in", value: [] }; // value: [{id, display_name}]
        default:
            return { operator: "=", value: "" };
    }
}

/** Is this single condition worth pushing (non-empty)? */
export function isConditionActive(kind, condition) {
    if (!condition) {
        return false;
    }
    switch (kind) {
        case "text":
            return String(condition.value ?? "").trim() !== "";
        case "numeric":
            if (condition.operator === "between") {
                return condition.value !== "" && condition.value2 !== "";
            }
            return condition.value !== "" && condition.value !== null;
        case "date":
            return Boolean(condition.value) || Boolean(condition.value2);
        case "boolean":
            return condition.value === true || condition.value === false;
        case "selection":
        case "many2one":
        case "many2many":
            return Array.isArray(condition.value) && condition.value.length > 0;
        default:
            return false;
    }
}

/**
 * Build the leaf list (implicitly AND-ed) for a single condition.
 * @returns {Array} an Odoo domain (list of leaves / prefix operators)
 */
function conditionToDomain(kind, fieldName, condition) {
    switch (kind) {
        case "text": {
            const raw = String(condition.value ?? "").trim();
            if (condition.operator === "=like_start") {
                return [[fieldName, "=like", `${raw}%`]];
            }
            return [[fieldName, condition.operator, raw]];
        }
        case "numeric": {
            if (condition.operator === "between") {
                return combine("&", [
                    [[fieldName, ">=", Number(condition.value)]],
                    [[fieldName, "<=", Number(condition.value2)]],
                ]);
            }
            return [[fieldName, condition.operator, Number(condition.value)]];
        }
        case "date": {
            const leaves = [];
            if (condition.value) {
                leaves.push([[fieldName, ">=", condition.value]]);
            }
            if (condition.value2) {
                leaves.push([[fieldName, "<=", condition.value2]]);
            }
            return combine("&", leaves);
        }
        case "boolean":
            return [[fieldName, "=", condition.value === true]];
        case "selection":
            return [[fieldName, "in", condition.value]];
        case "many2one":
        case "many2many":
            return [[fieldName, "in", condition.value.map((r) => r.id)]];
        default:
            return [];
    }
}

/**
 * Combine several sub-domains with a prefix operator ("&" or "|").
 * Each sub-domain must itself be a valid (already-normalised) domain list.
 */
export function combine(operator, domains) {
    const valid = domains.filter((d) => Array.isArray(d) && d.length);
    if (!valid.length) {
        return [];
    }
    return valid.reduce((acc, d) => (acc.length ? [operator, ...acc, ...d] : [...d]));
}

/**
 * Full domain for one column: OR of all its active conditions.
 */
export function buildFieldDomain(kind, fieldName, conditions) {
    const active = conditions.filter((c) => isConditionActive(kind, c));
    const subDomains = active.map((c) => conditionToDomain(kind, fieldName, c));
    return combine("|", subDomains);
}

/**
 * Human-readable facet label, e.g. "Salesperson: Mitchell or Marc".
 */
export function describeConditions(kind, label, conditions, field) {
    const active = conditions.filter((c) => isConditionActive(kind, c));
    const parts = active.map((c) => describeOne(kind, c, field));
    return `${label}: ${parts.join(" or ")}`;
}

function describeOne(kind, condition, field) {
    switch (kind) {
        case "text": {
            const opLabel = (TEXT_OPERATORS.find((o) => o.op === condition.operator) || {}).label || "";
            return `${opLabel} "${condition.value}"`.trim();
        }
        case "numeric": {
            if (condition.operator === "between") {
                return `${condition.value}…${condition.value2}`;
            }
            const opLabel = (NUMERIC_OPERATORS.find((o) => o.op === condition.operator) || {}).label || "";
            return `${opLabel} ${condition.value}`.trim();
        }
        case "date": {
            if (condition.value && condition.value2) {
                return `${condition.value} → ${condition.value2}`;
            }
            return condition.value ? `from ${condition.value}` : `until ${condition.value2}`;
        }
        case "boolean":
            return condition.value ? "Yes" : "No";
        case "selection": {
            const labels = (field.selection || [])
                .filter(([v]) => condition.value.includes(v))
                .map(([, l]) => l);
            return labels.join(", ");
        }
        case "many2one":
        case "many2many":
            return condition.value.map((r) => r.display_name).join(", ");
        default:
            return "";
    }
}
