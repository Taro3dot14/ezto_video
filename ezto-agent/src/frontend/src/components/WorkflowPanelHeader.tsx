import PanelCollapseToggle from "./PanelCollapseToggle";



export type PanelVariant = "plan" | "think";



interface Props {

  variant: PanelVariant;

  title: string;

  kicker: string;

  subtitle: string;

  metaActive: number | string;

  metaTotal: number | string;

  metaLabel: string;

  expanded: boolean;

  onToggle: () => void;

  expandLabel: string;

  collapseLabel: string;

  controlsId: string;

}



function PanelIcon({ variant }: { variant: PanelVariant }) {

  if (variant === "plan") {

    return (

      <svg className="wf-panel-title-svg" viewBox="0 0 24 24" aria-hidden>

        <path

          d="M8 6h11M8 12h11M8 18h7"

          fill="none"

          stroke="currentColor"

          strokeWidth="2"

          strokeLinecap="round"

        />

        <circle cx="4" cy="6" r="1.5" fill="currentColor" />

        <circle cx="4" cy="12" r="1.5" fill="currentColor" />

        <circle cx="4" cy="18" r="1.5" fill="currentColor" />

      </svg>

    );

  }



  return (

    <svg className="wf-panel-title-svg" viewBox="0 0 24 24" aria-hidden>

      <path

        d="M4 15c2.5-4 4-6 8-6s5.5 2 8 6"

        fill="none"

        stroke="currentColor"

        strokeWidth="2"

        strokeLinecap="round"

      />

      <path

        d="M7 18h10"

        fill="none"

        stroke="currentColor"

        strokeWidth="2"

        strokeLinecap="round"

      />

      <circle cx="12" cy="8" r="2" fill="currentColor" />

    </svg>

  );

}



export default function WorkflowPanelHeader({

  variant,

  title,

  kicker,

  subtitle,

  metaActive,

  metaTotal,

  metaLabel,

  expanded,

  onToggle,

  expandLabel,

  collapseLabel,

  controlsId,

}: Props) {

  return (

    <div className={`wf-panel-head wf-panel-head-${variant}`}>

      <div className="wf-panel-title-group">

        <span className="wf-panel-title-icon" aria-hidden>

          <PanelIcon variant={variant} />

        </span>

        <div className="wf-panel-title-copy">

          <span className="wf-panel-kicker">{kicker}</span>

          <div className="wf-panel-title-line">

            <h2 className="wf-panel-title">{title}</h2>

            <p className="wf-panel-sub">{subtitle}</p>

            <PanelCollapseToggle

              className="wf-panel-inline-toggle"

              expanded={expanded}

              onToggle={onToggle}

              expandLabel={expandLabel}

              collapseLabel={collapseLabel}

              controlsId={controlsId}

            />

          </div>

        </div>

      </div>



      <div className="wf-panel-head-end">

        <div className="wf-panel-meta-pill" aria-label={`${metaActive} / ${metaTotal} ${metaLabel}`}>

          <span className="wf-panel-meta-count">

            {metaActive}

            <span className="wf-panel-meta-sep">/</span>

            {metaTotal}

          </span>

          <span className="wf-panel-meta-label">{metaLabel}</span>

        </div>

      </div>

    </div>

  );

}

