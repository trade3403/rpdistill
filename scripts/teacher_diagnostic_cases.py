"""Original bilingual diagnostic, not an independently human-reviewed benchmark."""
from rpdistill.evaluation import clean_case,hash_json

# Domain, original source, authored reference, one terminology mapping, protected literals.
ROWS=[
("medicine","The patient received 5 mg of the drug every 8 hours.","患者每8小时接受5 mg该药物。","drug",["药物","药"],["5 mg"]),
("medicine","The samples were stored at 4 degrees Celsius to reduce degradation.","样品储存在4摄氏度以减少降解。","degradation",["降解","分解"],[]),
("medicine","The confidence interval was 95% in the primary analysis. [12]","主要分析中的置信区间为95%。 [12]","confidence interval",["置信区间"],["95%","[12]"]),
("medicine","The placebo group showed no significant improvement in symptoms.","安慰剂组的症状没有显著改善。","placebo group",["安慰剂组"],[]),
("chemistry","The reaction was conducted at 300 K under nitrogen.","反应在氮气环境中于300 K进行。","nitrogen",["氮气","氮"],["300 K"]),
("chemistry","The concentration of NaCl was 0.5 mol/L.","NaCl的浓度为0.5 mol/L。","concentration",["浓度"],["NaCl","0.5 mol/L"]),
("chemistry","The catalyst reduced the activation energy without changing the equilibrium.","催化剂降低了活化能，但未改变平衡。","activation energy",["活化能"],[]),
("chemistry","The pH of the solution decreased from 7.4 to 6.8.","溶液的pH从7.4降至6.8。","solution",["溶液"],["pH"]),
("biology","The expression of the gene increased after 24 hours of exposure.","暴露24小时后，该基因的表达量增加。","expression",["表达"],[]),
("biology","The mitochondrial membrane potential was measured using a fluorescent probe.","使用荧光探针测量线粒体膜电位。","mitochondrial membrane potential",["线粒体膜电位"],[]),
("biology","The enzyme activity decreased by 20% at low temperature.","低温下酶活性降低了20%。","enzyme activity",["酶活性","酶的活性"],["20%"]),
("biology","The DNA fragments were separated by gel electrophoresis. [7]","采用凝胶电泳分离DNA片段。 [7]","gel electrophoresis",["凝胶电泳"],["DNA","[7]"]),
("physics","The mean particle diameter was 12 nm before the treatment.","处理前粒子的平均直径为12 nm。","particle diameter",["粒径","粒子直径","颗粒直径","粒子的平均直径","颗粒的平均直径"],["12 nm"]),
("physics","The electric field was set to 10 V/m in the simulation.","模拟中的电场强度设为10 V/m。","electric field",["电场"],["10 V/m"]),
("physics","The force is proportional to the acceleration when the mass is constant.","质量恒定时，力与加速度成正比。","acceleration",["加速度"],[]),
("physics","The relation E=mc^2 connects mass and energy.","关系式E=mc^2将质量与能量联系起来。","energy",["能量"],["E=mc^2"]),
("computing","The Transformer uses multi-head attention to process the input sequence.","Transformer利用多头注意力处理输入序列。","multi-head attention",["多头注意力"],["Transformer"]),
("computing","The learning rate was reduced to 0.001 after 10 epochs.","训练10个轮次后，学习率降至0.001。","learning rate",["学习率"],[]),
("computing","The algorithm requires less memory than the baseline method. [3]","与基线方法相比，该算法需要更少的内存。 [3]","baseline",["基线","基准"],["[3]"]),
("computing","The model achieved an accuracy of 92% on the validation set.","模型在验证集上的准确率达到92%。","validation set",["验证集"],["92%"]),
("statistics","The null hypothesis was not rejected at the significance level of 0.05.","在0.05的显著性水平下，未拒绝原假设。","null hypothesis",["原假设","零假设"],[]),
("statistics","The standard deviation was 2.5 in the control group.","对照组的标准差为2.5。","standard deviation",["标准差"],[]),
("statistics","The sample size was 120 and the response rate was 80%.","样本量为120，应答率为80%。","sample size",["样本量","样本大小"],["80%"]),
("statistics","The regression coefficient remained positive after adjustment for age.","校正年龄后，回归系数仍为正。","regression coefficient",["回归系数"],[]),
]

def cases():
    rows=[]
    for i,(domain,source,ref,term,targets,protected) in enumerate(ROWS,1):
        rows.append(clean_case({"id":f"diagnostic-{i:03d}","paper_id":"fictional-domain-"+domain,
            "source":source,"reference":ref,"terms":[{"source":term,"targets":targets}],
            "protected":protected,"rights_note":"Original authored diagnostic; not independently human reviewed."}))
    return rows

def fixture_id():
    return hash_json(cases())
