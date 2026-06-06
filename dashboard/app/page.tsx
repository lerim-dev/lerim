import { redirect } from "next/navigation";

export default async function Home({
	searchParams,
}: {
	searchParams?: Promise<Record<string, string | string[] | undefined>>;
}) {
	const params = searchParams ? await searchParams : {};
	const rawProject = params.project;
	const project = Array.isArray(rawProject) ? rawProject[0] : rawProject;
	redirect(project ? `/overview?project=${encodeURIComponent(project)}` : "/overview");
}
