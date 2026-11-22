const { test } = require('node:test');
const assert = require('node:assert/strict');
const { mkdtemp, rm, writeFile } = require('node:fs/promises');
const { tmpdir } = require('node:os');
const { join } = require('node:path');
require('reflect-metadata');
const { ProjectsService } = require('../dist/projects.service');

test('project topics are searchable and exposed in catalog and detail', async () => {
  const directory = await mkdtemp(join(tmpdir(), 'radar-topics-'));
  const previous = process.env.PROJECTS_FILE;
  try {
    const file = join(directory, 'projects.json');
    await writeFile(file, JSON.stringify({ projects: [
      { project_title: 'Projekt', domain_tags: ['Edukacja'], keywords: ['robotyka'] },
      { project_title: 'Starszy projekt' },
    ] }));
    process.env.PROJECTS_FILE = file;
    const service = new ProjectsService();
    assert.equal((await service.search('robotyka', [])).length, 1);
    assert.equal((await service.catalog('edukacja')).total, 1);
    const catalog = await service.catalog('');
    assert.deepEqual(catalog.items[0].domain_tags, ['Edukacja']);
    assert.deepEqual(catalog.items[0].keywords, ['robotyka']);
    assert.deepEqual(catalog.items[1].keywords, []);
    const detail = await service.detail(catalog.items[0].id);
    assert.deepEqual(detail.innovation.domain_tags, ['Edukacja']);
    assert.deepEqual(detail.innovation.keywords, ['robotyka']);
  } finally {
    if (previous === undefined) delete process.env.PROJECTS_FILE;
    else process.env.PROJECTS_FILE = previous;
    await rm(directory, { recursive: true, force: true });
  }
});

test('keyword matches rank ahead of other fields in search and catalog', async () => {
  const directory = await mkdtemp(join(tmpdir(), 'radar-ranking-'));
  const previous = process.env.PROJECTS_FILE;
  try {
    const file = join(directory, 'projects.json');
    await writeFile(file, JSON.stringify({ projects: [
      { uuid: 'description', project_title: 'Inny projekt', summary: 'Portal funduszy' },
      { uuid: 'keywords', project_title: 'Portal Funduszy Europejskich', keywords: ['portal', 'funduszy'] },
      { uuid: 'partial', keywords: ['portal'] },
    ] }));
    process.env.PROJECTS_FILE = file;
    const service = new ProjectsService();
    const search = await service.search('PORTAL funduszy', []);
    assert.deepEqual(search.map((item) => item.project.uuid), ['keywords', 'description', 'partial']);
    assert.deepEqual(search[0].matchedTerms, ['portal', 'funduszy']);
    assert.deepEqual((await service.catalog('portal funduszy')).items.map((item) => item.id),
      ['keywords', 'description', 'partial']);
    assert.deepEqual((await service.catalog('')).items.map((item) => item.id),
      ['description', 'keywords', 'partial']);
  } finally {
    if (previous === undefined) delete process.env.PROJECTS_FILE;
    else process.env.PROJECTS_FILE = previous;
    await rm(directory, { recursive: true, force: true });
  }
});

test('agent-format project retains its fields across search, catalog and detail', async () => {
  const directory = await mkdtemp(join(tmpdir(), 'radar-agent-format-'));
  const previous = process.env.PROJECTS_FILE;
  try {
    const file = join(directory, 'projects.json');
    await writeFile(file, JSON.stringify({ projects: [{
      uuid: '03ca3e3a-7e16-5e1a-a043-a44a76770c0d',
      title: 'Portal Funduszy Europejskich', project_title: 'Portal Funduszy Europejskich',
      summary: 'Fragment artykułu o projektach medycznych',
      keywords: ['portal', 'funduszy', 'europejskich'], domain_tags: ['Zdrowie'],
      url: 'https://funduszeeuropejskie.gov.pl/', source_title: 'Portal Funduszy Europejskich',
      evidence: ['Fragment artykułu o projektach medycznych'],
      assessment: { score: null, coverage: 0, status: 'uncertain', dimensions: [], missing_questions: [] },
      prior_art: { status: 'matches_found', matches: [{ title: 'Publikacja', source: 'crossref' }] },
    }] }));
    process.env.PROJECTS_FILE = file;
    const service = new ProjectsService();
    const results = await service.search('portal funduszy', []);
    assert.equal(results[0].project.project_title, 'Portal Funduszy Europejskich');
    assert.deepEqual(results[0].matchedTerms, ['portal', 'funduszy']);
    const detail = await service.detail(results[0].project.uuid);
    assert.deepEqual(detail.innovation.keywords, results[0].project.keywords);
    assert.deepEqual(detail.innovation.prior_art, results[0].project.prior_art);
    assert.deepEqual(detail.assessment, results[0].project.assessment);
    assert.equal(detail.innovation.source_url, results[0].project.url);
    assert.equal((await service.catalog('portal funduszy')).items[0].id, results[0].project.uuid);
  } finally {
    if (previous === undefined) delete process.env.PROJECTS_FILE;
    else process.env.PROJECTS_FILE = previous;
    await rm(directory, { recursive: true, force: true });
  }
});
