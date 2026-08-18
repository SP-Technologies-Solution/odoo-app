/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { Many2XFilterInput } from "./widgets/many2x_filter_input";
import {
    NUMERIC_OPERATORS,
    TEXT_OPERATORS,
    defaultCondition,
    isConditionActive,
    widgetKindForField,
} from "./utils/domain_builder";

/**
 * The popover anchored under a column header. It hosts one or more condition
 * rows whose input adapts to the column's field type, plus the
 * Add-condition / Clear-all / Apply controls.
 *
 * Props:
 *   - fieldName, label, field (the field definition)
 *   - manager (ColumnFilterManager)
 *   - close  (() => void) provided by the popover service
 */
export class ColumnFilterPopover extends Component {
    static template = "sp_list_view_advanced_search.ColumnFilterPopover";
    static components = { Many2XFilterInput };
    static props = {
        fieldName: String,
        label: String,
        field: Object,
        manager: Object,
        close: { type: Function, optional: true },
    };

    setup() {
        this.kind = widgetKindForField(this.props.field);
        this.textOperators = TEXT_OPERATORS;
        this.numericOperators = NUMERIC_OPERATORS;

        const existing = this.props.manager.getEntry(this.props.fieldName);
        const conditions =
            existing && existing.conditions.length
                ? existing.conditions.map((c) => ({ ...c }))
                : [defaultCondition(this.kind, this.props.field)];
        this.state = useState({ conditions });
    }

    get selectionOptions() {
        return this.props.field.selection || [];
    }

    get allowsMultipleConditions() {
        // Booleans and multi-select selections don't benefit from stacking.
        return !["boolean"].includes(this.kind);
    }

    addCondition() {
        this.state.conditions.push(defaultCondition(this.kind, this.props.field));
    }

    removeCondition(index) {
        this.state.conditions.splice(index, 1);
        if (!this.state.conditions.length) {
            this.state.conditions.push(defaultCondition(this.kind, this.props.field));
        }
    }

    // --- input handlers -----------------------------------------------------

    setOperator(index, operator) {
        this.state.conditions[index].operator = operator;
    }

    setValue(index, value) {
        this.state.conditions[index].value = value;
    }

    setValue2(index, value) {
        this.state.conditions[index].value2 = value;
    }

    toggleSelection(index, optionValue) {
        const cond = this.state.conditions[index];
        const values = cond.value.includes(optionValue)
            ? cond.value.filter((v) => v !== optionValue)
            : [...cond.value, optionValue];
        cond.value = values;
    }

    isSelected(index, optionValue) {
        return this.state.conditions[index].value.includes(optionValue);
    }

    updateRelation(index, records) {
        this.state.conditions[index].value = records;
    }

    setBoolean(index, value) {
        this.state.conditions[index].value = value;
    }

    // --- footer actions -----------------------------------------------------

    get hasActiveCondition() {
        return this.state.conditions.some((c) => isConditionActive(this.kind, c));
    }

    apply() {
        this.props.manager.apply(this.props.fieldName, {
            kind: this.kind,
            label: this.props.label,
            field: this.props.field,
            conditions: this.state.conditions.filter((c) => isConditionActive(this.kind, c)),
        });
        this.props.close?.();
    }

    clearAll() {
        this.props.manager.apply(this.props.fieldName, {
            kind: this.kind,
            label: this.props.label,
            field: this.props.field,
            conditions: [],
        });
        this.props.close?.();
    }
}
