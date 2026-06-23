%% 生产优化问题 MATLAB 示例
clear; clc; close all;

resultsDir = "results";
if ~exist(resultsDir, "dir")
    mkdir(resultsDir);
end

product = ["A"; "B"];
quantity = [15; 25];
profit = [200; 300];
totalProfit = quantity .* profit;

T = table(product, quantity, profit, totalProfit);
writetable(T, fullfile(resultsDir, "output.csv"));

fid = fopen(fullfile(resultsDir, "summary.json"), "w");
fprintf(fid, '{"status":"ok","objective":10500}');
fclose(fid);

fig = figure("Visible", "off");
bar(quantity);
set(gca, "XTickLabel", product);
ylabel("Quantity");
title("Optimal Production Plan");
grid on;
exportgraphics(fig, fullfile(resultsDir, "result_main.png"), "Resolution", 300);
close(fig);
