/**
 * Score Gauge Component
 * Renders a circular score indicator with color coding.
 */

function renderScoreGauge(container, score, grade) {
  score = Number(score) || 0;
  const colorClass = score >= 80 ? 'great' : score >= 50 ? 'good' : 'poor';
  const label = score >= 80 ? 'Great Deal' : score >= 50 ? 'Good Deal' : 'Below Average';

  container.textContent = '';

  const gauge = document.createElement('div');
  gauge.className = 'score-gauge';

  const circle = document.createElement('div');
  circle.className = `score-gauge__circle score-gauge__circle--${colorClass}`;

  const number = document.createElement('div');
  number.className = 'score-gauge__number';
  number.textContent = score;

  const gradeEl = document.createElement('div');
  gradeEl.className = 'score-gauge__grade';
  gradeEl.textContent = String(grade);

  circle.appendChild(number);
  circle.appendChild(gradeEl);

  const labelEl = document.createElement('div');
  labelEl.className = 'score-gauge__label';
  labelEl.textContent = label;

  gauge.appendChild(circle);
  gauge.appendChild(labelEl);
  container.appendChild(gauge);
}
