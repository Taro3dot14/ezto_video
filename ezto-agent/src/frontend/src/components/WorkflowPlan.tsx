import { useMemo, useState } from "react";
import { displayPhaseLabel, NODE_META } from "../workflow/nodeCatalog";
import {
  buildPlanStepStatuses,
  planMetaCounts,
  type PlanStepStatus,
} from "../workflow/planProgress";
import WorkflowPanelHeader from "./WorkflowPanelHeader";

export type { PlanStepStatus };

export interface PlanMilestone {
  node: string;
  label: string;
}

interface PlanStep extends PlanMilestone {
  status: PlanStepStatus;
  index: number;
}

interface Props {
  milestones: PlanMilestone[];
  planOrder: string[];
  completedNodes: string[];
  currentNode: string | null;
}

function StepIcon({ status }: { status: PlanStepStatus }) {
  if (status === "done") {
    return (
      <svg className="wf-plan-svg wf-plan-svg-done" viewBox="0 0 20 20" aria-hidden>
        <circle cx="10" cy="10" r="9" fill="currentColor" opacity="0.15" />
        <path
          d="M6.5 10.2 8.8 12.5 13.5 7.8"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    );
  }
  if (status === "current") {
    return (
      <span className="wf-plan-icon-current" aria-hidden>
        <svg className="wf-plan-svg wf-plan-svg-current" viewBox="0 0 20 20">
          <circle cx="10" cy="10" r="7" fill="currentColor" opacity="0.2" />
          <circle cx="10" cy="10" r="4" fill="currentColor" />
        </svg>
      </span>
    );
  }
  return (
    <svg className="wf-plan-svg wf-plan-svg-pending" viewBox="0 0 20 20" aria-hidden>
      <circle
        cx="10"
        cy="10"
        r="7"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        opacity="0.35"
      />
    </svg>
  );
}

export default function WorkflowPlan({
  milestones,
  planOrder,
  completedNodes,
  currentNode,
}: Props) {
  const [expanded, setExpanded] = useState(true);

  const steps = useMemo((): PlanStep[] => {
    const statuses = buildPlanStepStatuses(planOrder, completedNodes, currentNode);
    return milestones.map((m, index) => ({
      ...m,
      status: statuses[index] ?? "pending",
      index,
    }));
  }, [milestones, planOrder, completedNodes, currentNode]);

  const { active: metaActive, total: metaTotal } = useMemo(
    () => planMetaCounts(planOrder, completedNodes, currentNode),
    [planOrder, completedNodes, currentNode],
  );

  const doneCount = steps.filter((s) => s.status === "done").length;
  const currentStep = steps.find((s) => s.status === "current");
  const progressPct = Math.round(
    ((doneCount + (currentStep ? 0.35 : 0)) / steps.length) * 100,
  );

  const phases = useMemo(() => {
    const groups: {
      phase: string;
      label: string;
      status: "done" | "current" | "pending";
      steps: PlanStep[];
    }[] = [];
    for (const step of steps) {
      const phase = NODE_META[step.node]?.phase ?? "phase1";
      const last = groups[groups.length - 1];
      if (last?.phase === phase) {
        last.steps.push(step);
      } else {
        groups.push({
          phase,
          label: displayPhaseLabel(phase),
          status: "pending",
          steps: [step],
        });
      }
    }
    for (const group of groups) {
      const hasCurrent = group.steps.some((s) => s.status === "current");
      const allDone = group.steps.every((s) => s.status === "done");
      group.status = hasCurrent ? "current" : allDone ? "done" : "pending";
    }
    return groups;
  }, [steps]);

  return (
    <section
      className={`wf-panel-card wf-plan${expanded ? " is-expanded" : " is-collapsed"}`}
      aria-label="工作流计划"
    >
      <WorkflowPanelHeader
        variant="plan"
        title="计划"
        kicker="全局进度"
        subtitle={
          currentStep
            ? `进行中 · ${currentStep.label}`
            : doneCount === steps.length
              ? "全部完成"
              : "等待下一步"
        }
        metaActive={metaActive}
        metaTotal={metaTotal}
        metaLabel="步骤"
        expanded={expanded}
        onToggle={() => setExpanded((v) => !v)}
        expandLabel="展开完整计划"
        collapseLabel="收起完整计划"
        controlsId="wf-plan-body"
      />

      <div id="wf-plan-body" className="wf-panel-body">
        <div className="wf-panel-body-inner">
          <div className="wf-panel-scroll">
            <div
              className="wf-plan-progress-track"
              role="progressbar"
              aria-valuenow={progressPct}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-label="计划完成进度"
            >
              <div
                className="wf-plan-progress-fill"
                style={{ width: `${progressPct}%` }}
              />
            </div>

            <div className="wf-plan-timeline">
              {phases.map((group) => (
                <div
                  key={group.phase}
                  className={`wf-plan-phase wf-plan-phase--${group.status}`}
                >
                  <div className="wf-plan-phase-label">{group.label}</div>
                  <ol className="wf-plan-steps">
                    {group.steps.map((step) => (
                      <li
                        key={step.node}
                        className={`wf-plan-step wf-plan-${step.status}`}
                        aria-current={step.status === "current" ? "step" : undefined}
                      >
                        <span className="wf-plan-marker">
                          <StepIcon status={step.status} />
                        </span>
                        <span className="wf-plan-label">
                          {String(step.index + 1).padStart(2, "0")}. {step.label}
                        </span>
                      </li>
                    ))}
                  </ol>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
