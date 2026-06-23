import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";

interface ProjectListContextValue {
  revision: number;
  refreshProjects: () => void;
}

const ProjectListContext = createContext<ProjectListContextValue | null>(null);

export function ProjectListProvider({ children }: { children: ReactNode }) {
  const [revision, setRevision] = useState(0);
  const refreshProjects = useCallback(() => {
    setRevision((n) => n + 1);
  }, []);

  const value = useMemo(
    () => ({ revision, refreshProjects }),
    [revision, refreshProjects],
  );

  return (
    <ProjectListContext.Provider value={value}>
      {children}
    </ProjectListContext.Provider>
  );
}

export function useProjectList() {
  const ctx = useContext(ProjectListContext);
  if (!ctx) {
    throw new Error("useProjectList must be used within ProjectListProvider");
  }
  return ctx;
}
