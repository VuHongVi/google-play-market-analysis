#!/usr/bin/env node
// Generates the Google Play Power BI report pages (PBIR) from the approved spec in _brief/report-spec.md.
// Usage: node powerbi/tools/build_report.js powerbi/GooglePlay.Report
// Numbers in charts/cards come from model measures/columns; sentences match README.md (results/metrics.json).
'use strict';
const path = require('path');
const L = require('./pbir_lib');
const { C, M, hid, str, num, bool, color, measure, column, agg, colRef, rect, slot, chrome, container, run, textbox, accent, insight,
  kpiCard, axisFont, gridY, tableObjects, flagColor, slicer, catFilter, betweenFilter } = L;

const REPORT = path.resolve(process.argv[2] || path.join(__dirname, '..', 'GooglePlay.Report'));
const { pages, page } = L.createReport(5);
const named = (p, displayName) => ({ ...p, displayName });
const noLegend = [{ properties: { show: bool(false) } }];
const seriesFill = (t, c, value, hex) => ({ properties: { fill: color(hex) },
  selector: { data: [{ scopeId: { Comparison: { ComparisonKind: 0, Left: colRef(t, c), Right: { Literal: { Value: `'${value}'` } } } } }] } });

function panel(key, r, title, blocks, source, hex = C.orange) {
  const tint = hex === C.orange ? C.orangeTint : C.blueTint;
  return [
    accent(hid(key + ':bar'), { ...r, width: 8 }, hex),
    textbox(hid(key), { ...r, x: r.x + 8, width: r.width - 8 }, [
      { textRuns: [run(title, 18, { font: 'Segoe UI Semibold' })] },
      { textRuns: [run(' ', 8)] },
      ...blocks.flatMap(([label, text]) => [
        { textRuns: [run(label, 11, { font: 'Segoe UI Semibold', col: hex })] },
        { textRuns: [run(text, 14)] },
        { textRuns: [run(' ', 6)] },
      ]),
      { textRuns: [run('Source: ' + source, 10, { col: C.muted, italic: true })] },
    ], { bg: tint, alt: title }),
  ];
}

function scatter(key, r, t, labelCol, flag, title, subtitle, alt) {
  return container(hid(key), r, {
    visualType: 'scatterChart',
    query: { queryState: {
      Category: { projections: [named(column(t, labelCol), 'Segment')] },
      X: { projections: [named(agg(t, 'top_decile_share', 'Sum'), 'Installs taken by the top 10% of apps')] },
      Y: { projections: [named(agg(t, 'hit_rate', 'Sum'), 'Share of apps with 1M+ installs')] },
      Size: { projections: [named(agg(t, 'apps', 'Sum'), 'Apps')] },
      Tooltips: { projections: [named(agg(t, 'hit_rate_low', 'Sum'), 'Hit rate, 95% CI low'), named(agg(t, 'hit_rate_high', 'Sum'), 'Hit rate, 95% CI high'), named(agg(t, 'opportunity_rank', 'Min'), 'Opportunity rank')] },
    } },
    objects: {
      categoryAxis: [{ properties: { ...axisFont, showAxisTitle: bool(true), ...gridY } }],
      valueAxis: [{ properties: { ...axisFont, ...gridY, showAxisTitle: bool(true), start: num(0) } }],
      dataPoint: [{ properties: { defaultColor: color(C.blue) } }, flagColor(t, flag, C.orange, C.blue)],
      categoryLabels: [{ properties: { show: bool(true), fontSize: num(10), color: color(C.text) } }],
      bubbles: [{ properties: { bubbleSize: num(-20) } }],
      legend: noLegend,
    },
    visualContainerObjects: chrome({ title, subtitle, alt }),
  });
}

function rankTable(key, r, t, labelCol, labelName, extra, title, subtitle, filters) {
  return container(hid(key), r, {
    visualType: 'tableEx',
    query: { queryState: { Values: { projections: [
      named(column(t, 'opportunity_rank'), 'Rank'), named(column(t, labelCol), labelName), named(column(t, 'apps'), 'Apps'),
      named(column(t, 'hit_rate'), 'Hit rate'), named(column(t, 'top_decile_share'), 'Top-10% share'), named(column(t, extra[0]), extra[1]),
    ] } }, sortDefinition: { sort: [{ field: column(t, 'opportunity_rank').field, direction: 'Ascending' }], isDefaultSort: false } },
    objects: tableObjects(13),
    visualContainerObjects: chrome({ title, subtitle, alt: title }),
  }, filters ? { filterConfig: { filters } } : {});
}

function hitColumns(key, r, catCol, title, subtitle, alt, filters) {
  return container(hid(key), r, {
    visualType: 'clusteredColumnChart',
    query: { queryState: { Category: { projections: [column('fact_apps', catCol)] }, Y: { projections: [measure('Hit Rate')] }, Tooltips: { projections: [measure('Apps')] } },
      sortDefinition: { sort: [{ field: column('fact_apps', catCol).field, direction: 'Ascending' }], isDefaultSort: false } },
    objects: {
      categoryAxis: [{ properties: { ...axisFont, fontSize: num(11), showAxisTitle: bool(false) } }],
      valueAxis: [{ properties: { ...axisFont, ...gridY, showAxisTitle: bool(false), start: num(0) } }],
      dataPoint: [{ properties: { defaultColor: color(C.blue) } }],
      labels: [{ properties: { show: bool(true), fontSize: num(12), color: color(C.text) } }],
      legend: noLegend,
    },
    visualContainerObjects: chrome({ title, subtitle, alt }),
  }, filters ? { filterConfig: { filters } } : {});
}

// 1. Overview ------------------------------------------------------------------
page('overview', 'Overview', 'Overview', 'Build a free Racing, Role Playing or Strategy game', () => {
  const strip = rect([1, 2, 13, 4]);
  const cards = [
    ['Apps analysed', 'Apps', 'Unique apps after removing 1,181 duplicates.'],
    ['Games', 'Games', 'GAME apps + FAMILY apps with a game genre.'],
    ['Games filed under FAMILY', 'Games Filed Under Family %', 'Share of games a Category = GAME filter would miss.'],
    ['Hit rate, all apps', 'Hit Rate', 'Share of apps with 1M+ installs.'],
    ['Hit rate, games', 'Hit Rate Games', 'Share of games with 1M+ installs.'],
    ['Hit rate, paid apps', 'Paid Hit Rate', 'Free apps: 37.9%.'],
  ];
  return [
    ...cards.map((c, i) => kpiCard('overview:k:' + i, slot(strip, i, 6), ...c, 30)),
    container(hid('overview:filed'), rect([1, 4, 7, 13]), {
      visualType: 'barChart',
      query: { queryState: { Category: { projections: [column('fact_apps', 'primary_genre')] }, Y: { projections: [measure('Games')] }, Series: { projections: [column('fact_apps', 'game_filed_under')] } },
        sortDefinition: { sort: [{ field: measure('Games').field, direction: 'Descending' }], isDefaultSort: false } },
      objects: {
        categoryAxis: [{ properties: { ...axisFont, fontSize: num(11), showAxisTitle: bool(false) } }],
        valueAxis: [{ properties: { ...axisFont, ...gridY, showAxisTitle: bool(false) } }],
        dataPoint: [seriesFill('fact_apps', 'game_filed_under', 'Filed under GAME', C.blue), seriesFill('fact_apps', 'game_filed_under', 'Filed under FAMILY', C.orange)],
        legend: [{ properties: { show: bool(true), position: str('Top'), fontSize: num(11), labelColor: color(C.muted) } }],
      },
      visualContainerObjects: chrome({ title: 'Games by genre, and where Google Play files them', subtitle: 'Primary genre of each game. Orange = filed under FAMILY: a Category = GAME filter drops these, including most Casual, Puzzle, Simulation and Role Playing games.', alt: 'Stacked bars of games by genre split by GAME vs FAMILY category.' }),
    }, { filterConfig: { filters: [catFilter('overview:filed:game', 'fact_apps', 'is_game', '1L')] } }),
    ...panel('overview:rec', rect([7, 4, 13, 13]), 'Recommendation for a small studio', [
      ['BUILD', 'A free game in Racing, Role Playing or Strategy: the top opportunity ranks among game genres (high hit rate, least concentrated installs).'],
      ['AVOID', 'Puzzle, Board and Trivia games; Books & Reference, Medical, Events and Business apps.'],
      ['BUSINESS MODEL', 'Free + ads / in-app purchases: 37.9% of free apps reach 1M installs vs 2.9% of paid.'],
      ['OPERATE', 'Ship updates at least monthly (56.7% vs 18.5% hit rate by recency) and staff player support: game reviews are the most negative (35%).'],
      ['QUALITY BAR', '4.1-4.6 stars with 100+ reviews; hit rate peaks there.'],
      ['DATA CATCH', '775 of 1,720 games (45%) are filed under FAMILY, not GAME.'],
    ], 'README Recommendation (results/metrics.json)'),
  ];
});

// 2. App categories --------------------------------------------------------------
page('categories', 'App categories', 'App categories', 'Education, Weather and Photography are the most open app categories', () => [
  scatter('categories:map', rect([1, 2, 8, 13]), 'fact_category_scores', 'category_label', 'is_highlight', 'App categories: demand vs competition',
    'X = share of the category\'s installs taken by its top 10% of apps (lower = more open). Y = share of apps with 1M+ installs. Size = apps. Top-left is better; orange = Game.',
    'Scatter of 33 app categories by install concentration and hit rate.'),
  rankTable('categories:table', rect([8, 2, 13, 10]), 'fact_category_scores', 'category_label', 'Category', ['median_rating', 'Median rating'],
    'Top 10 categories by opportunity', 'Rank = hit-rate percentile + openness percentile; categories with 50+ apps.',
    [betweenFilter('categories:top10', 'fact_category_scores', 'opportunity_rank', '1L', '10L')]),
  ...insight('categories:i1', rect([8, 10, 13, 13]), 'Education: 58% of apps are hits and its top 10% take only 50% of installs. Business, Events and Medical sit bottom-right. Game (orange) has a 57% hit rate but its top 10% take 76%.', 'fact_category_scores.csv (results/category_scores.csv)'),
]);

// 3. Game genres -----------------------------------------------------------------
page('genres', 'Game genres', 'Game genres', 'Racing, Role Playing and Strategy: hits without a few titles owning the genre', () => [
  scatter('genres:map', rect([1, 2, 8, 13]), 'fact_genre_scores', 'primary_genre', 'is_recommended', 'Game genres: demand vs competition',
    'Games = GAME apps + FAMILY apps with a game genre; genres with 30+ games. Orange = top 3 by opportunity.',
    'Scatter of 13 game genres by install concentration and hit rate.'),
  rankTable('genres:table', rect([8, 2, 13, 10]), 'fact_genre_scores', 'primary_genre', 'Genre', ['paid_share', 'Paid share'],
    'Game genres by opportunity', 'Paid share = share of the genre\'s games sold up front.'),
  ...insight('genres:i1', rect([8, 10, 13, 13]), 'Racing: 69% of games reach 1M installs and the top 10% take 59%. Casual is popular but its top 10% take 84%: a new casual game competes with giants. Trivia is the worst bet (15% hits, 97% concentration).', 'fact_genre_scores.csv (results/game_genre_scores.csv)'),
]);

// 4. What makes a hit ---------------------------------------------------------------
page('drivers', 'What makes a hit', 'What makes a hit', 'Free, updated, rated 4.1-4.6', () => {
  const f = rect([5, 1, 9, 2]);
  const fr = { ...f, y: f.y - 8, height: 80 };
  return [
    slicer('drivers:type', slot(fr, 0, 2), 'fact_apps', 'app_type', 'App type (pick Game for games only)'),
    slicer('drivers:cat', slot(fr, 1, 2), 'fact_apps', 'category_label', 'Category'),
    hitColumns('drivers:rating', rect([1, 2, 5, 11]), 'rating_band', 'Hit rate by store rating', 'Apps with 100+ reviews, so the rating is stable.', 'Hit rate by rating band.',
      [betweenFilter('drivers:rating:band', 'fact_apps', 'rating_band_order', '1L', '5L')]),
    hitColumns('drivers:update', rect([5, 2, 9, 11]), 'update_age', 'Hit rate by days since last update', 'Days between the last update and the snapshot (2018-08-08).', 'Hit rate by update recency.'),
    hitColumns('drivers:price', rect([9, 2, 13, 11]), 'pricing', 'Hit rate: free vs paid', 'Paid = any up-front price.', 'Hit rate for free and paid apps.'),
    ...insight('drivers:i1', rect([1, 11, 13, 13]), 'All apps: the hit rate peaks at 4.4-4.6 stars (62%) and falls to 40% at 4.7-5.0, where small niche apps sit. Apps updated in the last 30 days are hits 3.1x as often as apps untouched for a year (57% vs 18%; causality runs both ways). Free apps hit 13x as often as paid (38% vs 2.9%). Use the slicers to see games or one category.', 'fact_apps.csv; correlations, not experiments'),
  ];
}, { headerCols: 5 });

// 5. Sentiment and limitations --------------------------------------------------------
page('sentiment', 'Sentiment and limitations', 'Sentiment and limitations', 'Game players complain the most, and this data has limits', () => {
  const lim = rect([7, 2, 13, 13]);
  const items = [
    '2018 snapshot: the winners will have moved; the method (hit rate vs concentration, with a clean game definition) is what transfers.',
    "The scrape over-represents visible, popular apps (median 100,000 installs), so hit rates are inflated. Compare segments; don't read them as real odds.",
    "Installs are lower bounds of buckets ('1,000,000+').",
    "No revenue column: 'hit' means installs, not money.",
    'Drivers are correlations: successful apps can afford more updates.',
    'Sentiment labels come with the dataset; only 1,074 apps have reviews.',
  ];
  return [
    container(hid('sentiment:bars'), rect([1, 2, 7, 11]), {
      visualType: 'clusteredBarChart',
      query: { queryState: { Category: { projections: [column('fact_category_sentiment', 'category_label')] }, Y: { projections: [measure('Negative Review Share')] } },
        sortDefinition: { sort: [{ field: measure('Negative Review Share').field, direction: 'Descending' }], isDefaultSort: false } },
      objects: {
        categoryAxis: [{ properties: { ...axisFont, fontSize: num(11), showAxisTitle: bool(false) } }],
        valueAxis: [{ properties: { ...axisFont, ...gridY, showAxisTitle: bool(false), start: num(0) } }],
        dataPoint: [{ properties: { defaultColor: color(C.blue) } }, flagColor('fact_category_sentiment', 'is_game', C.orange, C.blue)],
        labels: [{ properties: { show: bool(true), fontSize: num(11), color: color(C.text) } }],
        legend: noLegend,
      },
      visualContainerObjects: chrome({ title: 'Negative share of reviews by category', subtitle: 'Median, per app, of reviews labelled Negative; apps with 20+ labelled reviews, categories with 15+ such apps. Orange = Game.', alt: 'Bars of negative review share by category, Game highest.' }),
    }),
    ...insight('sentiment:i1', rect([1, 11, 7, 13]), 'Labels track star ratings (Spearman -0.23, 677 apps), so they are usable. The median game has 35% negative reviews vs 10% for Health & Fitness: support and bug fixes matter most in games.', 'fact_category_sentiment.csv (googleplaystore_user_reviews.csv)'),
    accent(hid('sentiment:bar'), { ...lim, width: 8 }, C.orange),
    textbox(hid('sentiment:limits'), { ...lim, x: lim.x + 8, width: lim.width - 8 }, [
      { textRuns: [run('Limitations', 18, { font: 'Segoe UI Semibold' })] },
      ...items.flatMap((t) => [{ textRuns: [run(' ', 8)] }, { textRuns: [run(t, 16)], listType: 'bullet', indent: 1 }]),
      { textRuns: [run(' ', 8)] },
      { textRuns: [run('Source: README Limitations; data: Kaggle lava18/google-play-store-apps', 10, { col: C.muted, italic: true })] },
    ], { bg: C.card, alt: 'Limitations of the Google Play data' }),
  ];
});

L.writeReport(REPORT, pages);
