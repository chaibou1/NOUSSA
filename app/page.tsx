'use client';

import { useState } from 'react';

interface Photo {
  filename: string;
  text: string;
}

interface Contributor {
  filename: string;
  name: string;
}

export default function Home() {
  const [photos, setPhotos] = useState<Photo[]>([]);
  const [contributors, setContributors] = useState<Contributor[]>([]);
  const [projectDescription, setProjectDescription] = useState(
    'Écrivez ici la présentation de votre projet étudiant, ses objectifs, ses technologies et ce qu’il apporte.'
  );

  const handlePhotoUpload = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    const response = await fetch('/api/photos', {
      method: 'POST',
      body: formData,
    });
    if (response.ok) {
      const data = await response.json();
      setPhotos((current) => [...current, data]);
      event.currentTarget.reset();
    }
  };

  const handleContributorUpload = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    const response = await fetch('/api/contributors', {
      method: 'POST',
      body: formData,
    });
    if (response.ok) {
      const data = await response.json();
      setContributors((current) => [...current, data]);
      event.currentTarget.reset();
    }
  };

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top_left,_rgba(99,102,241,0.15),_transparent_26%),_radial-gradient(circle_at_bottom_right,_rgba(56,189,248,0.15),_transparent_20%),_linear-gradient(180deg,_#f9fafb_0%,_#eef2ff_100%)] text-slate-900">
      <div className="mx-auto max-w-7xl px-6 py-12 md:px-8">
        <section className="grid gap-10 lg:grid-cols-[1.2fr_0.8fr] lg:items-center">
          <div className="space-y-8">
            <span className="inline-flex rounded-full bg-indigo-100 px-4 py-1 text-sm font-semibold uppercase tracking-[0.35em] text-indigo-700">
              Portfolio étudiant
            </span>
            <div className="max-w-2xl space-y-6">
              <h1 className="text-5xl font-extrabold tracking-tight text-slate-900 sm:text-6xl">
                Mettez en valeur vos projets, vos visuels et votre équipe.
              </h1>
              <p className="text-lg leading-8 text-slate-600">
                Créez un site de présentation clair, professionnel et inspirant pour vos projets scolaires ou personnels.
              </p>
            </div>
            <div className="grid gap-4 sm:grid-cols-3">
              <div className="card p-5">
                <p className="text-sm uppercase tracking-[0.28em] text-slate-500">Photos</p>
                <p className="mt-3 text-3xl font-semibold text-slate-950">{photos.length}</p>
              </div>
              <div className="card p-5">
                <p className="text-sm uppercase tracking-[0.28em] text-slate-500">Contributeurs</p>
                <p className="mt-3 text-3xl font-semibold text-slate-950">{contributors.length}</p>
              </div>
              <div className="card p-5">
                <p className="text-sm uppercase tracking-[0.28em] text-slate-500">Description</p>
                <p className="mt-3 text-3xl font-semibold text-slate-950">Rédigez plus vite</p>
              </div>
            </div>
          </div>

          <div className="card p-8">
            <div className="space-y-5">
              <h2 className="text-2xl font-semibold text-slate-950">Votre portfolio visuel</h2>
              <p className="text-slate-600">
                Utilisez ce template pour présenter rapidement votre projet avec un design propre et professionnel.
              </p>
            </div>
            <div className="mt-8 grid gap-4">
              <div className="card p-5">
                <p className="text-sm uppercase tracking-[0.28em] text-indigo-600">Projet</p>
                <h3 className="mt-3 text-xl font-semibold text-slate-950">Application Web</h3>
                <p className="mt-2 text-sm text-slate-500">Présentez l’interface, les pages principales et l’expérience utilisateur.</p>
              </div>
              <div className="card p-5">
                <p className="text-sm uppercase tracking-[0.28em] text-indigo-600">Équipe</p>
                <h3 className="mt-3 text-xl font-semibold text-slate-950">Contributeurs</h3>
                <p className="mt-2 text-sm text-slate-500">Montrez les membres et les rôles pour valoriser votre collaboration.</p>
              </div>
            </div>
          </div>
        </section>

        <section className="mt-16 grid gap-10 lg:grid-cols-[1.45fr_0.95fr]">
          <div className="rounded-[2rem] bg-white p-8 shadow-2xl shadow-slate-200/70">
            <div className="space-y-4">
              <span className="inline-flex rounded-full bg-violet-100 px-4 py-1 text-sm font-semibold uppercase tracking-[0.28em] text-violet-700">
                Description du projet
              </span>
              <h2 className="text-3xl font-semibold text-slate-950">Racontez votre projet</h2>
              <p className="text-slate-600">
                Expliquez le but, les fonctionnalités et les technologies utilisées. Cette présentation est votre vitrine étudiante.
              </p>
            </div>
            <textarea
              value={projectDescription}
              onChange={(e) => setProjectDescription(e.target.value)}
              className="mt-8 min-h-[200px] w-full rounded-[1.75rem] border border-slate-200 bg-slate-50 px-6 py-4 text-slate-900 shadow-sm outline-none transition focus:border-violet-400 focus:ring-4 focus:ring-violet-100"
            />
          </div>

          <aside className="space-y-6 rounded-[2rem] bg-gradient-to-br from-violet-600 via-indigo-600 to-sky-500 p-8 text-white shadow-2xl shadow-slate-700/30">
            <div className="space-y-3">
              <h3 className="text-2xl font-semibold">Ajoutez facilement vos contenus</h3>
              <p className="text-slate-100/90">
                Téléversez vos photos et les profils des contributeurs pour donner vie à votre page portfolio.
              </p>
            </div>

            <div className="space-y-5 rounded-[1.75rem] bg-white/10 p-6 shadow-inner shadow-slate-900/20">
              <h4 className="text-lg font-semibold">Photo du projet</h4>
              <form onSubmit={handlePhotoUpload} className="grid gap-4">
                <input
                  type="file"
                  name="file"
                  accept="image/*"
                  required
                  className="rounded-2xl border border-white/20 bg-white/10 px-4 py-3 text-sm text-white placeholder:text-slate-200/80 file:rounded-2xl file:border-0 file:bg-white file:text-slate-950 file:font-semibold"
                />
                <input
                  type="text"
                  name="text"
                  placeholder="Texte pour cette photo"
                  required
                  className="rounded-2xl border border-white/20 bg-white/10 px-4 py-3 text-sm text-white placeholder:text-slate-200/80"
                />
                <button
                  type="submit"
                  className="rounded-2xl bg-white px-5 py-3 text-sm font-semibold text-slate-950 transition hover:bg-slate-100"
                >
                  Ajouter une photo
                </button>
              </form>
            </div>

            <div className="space-y-5 rounded-[1.75rem] bg-white/10 p-6 shadow-inner shadow-slate-900/20">
              <h4 className="text-lg font-semibold">Contributeur</h4>
              <form onSubmit={handleContributorUpload} className="grid gap-4">
                <input
                  type="text"
                  name="name"
                  placeholder="Nom du contributeur"
                  required
                  className="rounded-2xl border border-white/20 bg-white/10 px-4 py-3 text-sm text-white placeholder:text-slate-200/80"
                />
                <input
                  type="file"
                  name="file"
                  accept="image/*"
                  required
                  className="rounded-2xl border border-white/20 bg-white/10 px-4 py-3 text-sm text-white placeholder:text-slate-200/80 file:rounded-2xl file:border-0 file:bg-white file:text-slate-950 file:font-semibold"
                />
                <button
                  type="submit"
                  className="rounded-2xl bg-white px-5 py-3 text-sm font-semibold text-slate-950 transition hover:bg-slate-100"
                >
                  Ajouter un membre
                </button>
              </form>
            </div>
          </aside>
        </section>

        <section className="mt-16">
          <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
            <div>
              <p className="text-sm font-semibold uppercase tracking-[0.28em] text-violet-600">Galerie</p>
              <h2 className="mt-3 text-3xl font-semibold text-slate-950">Photos du projet</h2>
            </div>
            <p className="max-w-xl text-sm leading-6 text-slate-600 md:text-right">
              Chaque visuel peut être accompagné d’un texte pour expliquer le contexte ou la fonctionnalité présentée.
            </p>
          </div>

          <div className="mt-8 grid gap-5 sm:grid-cols-2 xl:grid-cols-3">
            {photos.length === 0 ? (
              <div className="col-span-full rounded-[2rem] border border-dashed border-slate-300 bg-white/80 p-12 text-center text-slate-500">
                Aucune photo ajoutée pour le moment. Téléversez votre première image pour la voir ici.
              </div>
            ) : (
              photos.map((photo, index) => (
                <article key={index} className="overflow-hidden rounded-[2rem] border border-slate-200 bg-white shadow-lg shadow-slate-200/70 transition hover:-translate-y-1 hover:shadow-xl">
                  <img src={`/uploads/${photo.filename}`} alt={photo.text} className="h-72 w-full object-cover" />
                  <div className="space-y-3 p-5">
                    <p className="text-sm uppercase tracking-[0.24em] text-violet-600">Photo projet</p>
                    <p className="text-slate-700">{photo.text}</p>
                  </div>
                </article>
              ))
            )}
          </div>
        </section>

        <section className="mt-16 rounded-[2rem] bg-white p-8 shadow-2xl shadow-slate-200/80">
          <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
            <div>
              <p className="text-sm font-semibold uppercase tracking-[0.28em] text-slate-500">Contributeurs</p>
              <h2 className="mt-3 text-3xl font-semibold text-slate-950">L’équipe du projet</h2>
            </div>
            <p className="max-w-xl text-sm leading-6 text-slate-600 md:text-right">
              Ajoutez un profil pour chaque membre afin de montrer qui a participé et quel rôle chacun a joué.
            </p>
          </div>

          <div className="mt-10 grid gap-5 sm:grid-cols-2 xl:grid-cols-3">
            {contributors.length === 0 ? (
              <div className="col-span-full rounded-[1.75rem] border border-dashed border-slate-300 bg-slate-50 p-12 text-center text-slate-500">
                Aucun contributeur ajouté pour le moment. Ajoutez un profil pour le voir ici.
              </div>
            ) : (
              contributors.map((contributor, index) => (
                <div key={index} className="rounded-[1.75rem] border border-slate-200 bg-slate-50 p-6 text-center shadow-sm shadow-slate-200/70">
                  <div className="mx-auto mb-4 h-28 w-28 overflow-hidden rounded-full border-4 border-white bg-slate-100">
                    <img src={`/uploads/${contributor.filename}`} alt={contributor.name} className="h-full w-full object-cover" />
                  </div>
                  <p className="text-xl font-semibold text-slate-950">{contributor.name}</p>
                </div>
              ))
            )}
          </div>
        </section>
      </div>
    </main>
  );
}
