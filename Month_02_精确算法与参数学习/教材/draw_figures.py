from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon, Patch

out = Path(__file__).resolve().parent / 'figures'
out.mkdir(exist_ok=True)
plt.rcParams.update({'font.family':'DejaVu Sans', 'font.size':11, 'svg.fonttype':'none'})

fig, ax = plt.subplots(figsize=(9, 5.5), layout='constrained')
ax.add_patch(Polygon([(0,0),(50,0),(40,20),(0,40)], color='#bce2f5', alpha=.8, label='Feasible region'))
x = list(range(56))
ax.plot(x, [100-2*t for t in x], color='#206b9b', label='Machine: 2x + y = 100')
ax.plot(x, [(80-t)/2 for t in x], color='#be6a24', label='Labor: x + 2y = 80')
ax.plot(x, [(2200-40*t)/30 for t in x], '--', color='#922b57', label='Profit: 40x + 30y = 2200')
ax.scatter([0,50,40,0],[0,0,20,40], c='#17324d', zorder=4)
ax.annotate('Optimum (40, 20)\nProfit = 2200', (40,20), (5,43), arrowprops={'arrowstyle':'->'}, bbox={'facecolor':'white','edgecolor':'none','alpha':.95})
ax.set(xlim=(-2,55), ylim=(-2,49), xlabel='Product A quantity x', ylabel='Product B quantity y', title='One model: four feasible vertices')
ax.grid(alpha=.18); ax.legend(loc='upper right', fontsize=9)
fig.savefig(out/'lp_feasible_region.svg'); plt.close(fig)

fig, ax = plt.subplots(figsize=(9,5), layout='constrained')
ax.plot([0,40,160,200],[0,1200,3200,3200], color='#206b9b', linewidth=3)
ax.scatter([40,100,160],[1200,2200,3200],color='#922b57',zorder=4)
ax.axvspan(40,160,color='#bce2f5',alpha=.35)
ax.annotate('Slope = 30', (19,570), (4,1250), arrowprops={'arrowstyle':'->'})
ax.annotate('Slope = 50/3\nBasis remains valid', (90,2033), (67,1000), arrowprops={'arrowstyle':'->'})
ax.annotate('Slope = 0\nExtra machine hours have no value', (180,3200), (128,2400), arrowprops={'arrowstyle':'->'})
ax.annotate('Baseline (100, 2200)', (100,2200), (108,1770), arrowprops={'arrowstyle':'->'})
ax.set(xlim=(0,205),ylim=(0,3550),xlabel='Available machine hours b',ylabel='Optimal profit V(b)',title='Shadow prices are local slopes, not unlimited forecasts')
ax.grid(alpha=.18)
fig.savefig(out/'sensitivity.svg'); plt.close(fig)

fig, ax = plt.subplots(figsize=(9,3.7), layout='constrained')
colors={'J1':'#206b9b','J2':'#be6a24'}
for machine,start,duration,label,job in [(0,0,3,'J1 / O1','J1'),(1,3,2,'J1 / O2','J1'),(1,0,2,'J2 / O1','J2'),(0,3,1,'J2 / O2','J2')]:
    ax.barh(machine,duration,left=start,height=.55,color=colors[job],edgecolor='white')
    ax.text(start+duration/2,machine,label,ha='center',va='center',color='white',fontsize=10)
ax.axvline(5,color='#922b57',linestyle='--')
ax.set(yticks=[0,1],yticklabels=['M1','M2'],xticks=range(6),xlim=(0,5.6),ylim=(-.6,1.8),xlabel='Time',title='Job shop: machine exclusivity and job precedence')
ax.text(5.05,1.35,'Cmax = 5',color='#922b57')
ax.legend(handles=[Patch(color=c,label=j) for j,c in colors.items()],loc='upper left',ncols=2)
ax.grid(axis='x',alpha=.2)
fig.savefig(out/'jsp_gantt.svg'); plt.close(fig)
print('Created 3 textbook SVG figures.')
