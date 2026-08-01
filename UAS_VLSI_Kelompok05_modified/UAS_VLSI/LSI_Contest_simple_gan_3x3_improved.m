%% =========================================================
%  3x3 SimpleGAN - IMPROVED TRAINING (FORMAT PRESERVED)
%  [Better Generator Deception]
% =========================================================
clear; clc; close all;
rng(42);

% --- 1. Konfigurasi ---
latent_dim  = 2;
hidden_dim  = 3;
num_epochs  = 50000;

lr_G = 0.0015;      % Generator lebih agresif
lr_D = 0.0008;      % Discriminator dilemahkan sedikit

batch_size = 8;     % Mini-batch
log_interval = 1;

real_label = 0.9;   % Label smoothing
fake_label = 0.0;

sigma_noise = 0.05; % Instance noise awal

% --- 2. Dataset (0=Hitam, 1=Putih) ---
circle  = [1 0 1, 0 1 0, 1 0 1]';
cross   = [0 1 0, 1 0 1, 0 1 0]';
data    = [circle, cross];
N = size(data,2);

% --- 3. Inisialisasi Bobot (SAMA FORMAT) ---
scale = 0.5;
Wg1 = scale * randn(hidden_dim, latent_dim); bg1 = zeros(hidden_dim,1);
Wg2 = scale * randn(9, hidden_dim);          bg2 = zeros(9,1);

Wd1 = scale * randn(hidden_dim, 9);          bd1 = zeros(hidden_dim,1);
Wd2 = scale * randn(1, hidden_dim);          bd2 = 0;

% Aktivasi
sigmoid    = @(x) 1 ./ (1 + exp(-x));
tanh_f     = @(x) tanh(x);
d_sigmoid  = @(y) y .* (1 - y);
d_tanh     = @(y) 1 - y.^2;

loss_G_log = [];
loss_D_log = [];

fprintf('Training SimpleGAN (Improved)...\n');

%% =========================================================
%  4. TRAINING LOOP
%% =========================================================
for epoch = 1:num_epochs

    %% -------- Train Discriminator --------
    idx = randi(N,[1 batch_size]);
    x_real = data(:,idx);

    % Instance noise (anneal)
    noise_scale = sigma_noise * max(0,1 - epoch/(0.7*num_epochs));
    x_real = x_real + noise_scale * randn(size(x_real));

    % Generator forward
    z = randn(latent_dim,batch_size);
    h_g = tanh_f(Wg1*z + bg1);
    x_fake = sigmoid(Wg2*h_g + bg2);
    x_fake = x_fake + noise_scale * randn(size(x_fake));

    % Discriminator forward
    h_d_real = tanh_f(Wd1*x_real + bd1);
    a_real   = Wd2*h_d_real + bd2;
    y_real   = sigmoid(a_real);

    h_d_fake = tanh_f(Wd1*x_fake + bd1);
    a_fake   = Wd2*h_d_fake + bd2;
    y_fake   = sigmoid(a_fake);

    % ---- BCE gradient (STABLE FORM) ----
    dA_real = (y_real - real_label);
    dA_fake = (y_fake - fake_label);

    % Grad Wd2
    dWd2 = (dA_real*h_d_real' + dA_fake*h_d_fake') / batch_size;
    dbd2 = mean(dA_real + dA_fake);

    % Grad Wd1
    t_real = (Wd2'*dA_real) .* d_tanh(h_d_real);
    t_fake = (Wd2'*dA_fake) .* d_tanh(h_d_fake);

    dWd1 = (t_real*x_real' + t_fake*x_fake') / batch_size;
    dbd1 = mean(t_real + t_fake,2);

    % Update D
    Wd1 = Wd1 - lr_D*dWd1;
    bd1 = bd1 - lr_D*dbd1;
    Wd2 = Wd2 - lr_D*dWd2;
    bd2 = bd2 - lr_D*dbd2;

    %% -------- Train Generator --------
    z = randn(latent_dim,batch_size);
    h_g = tanh_f(Wg1*z + bg1);
    x_fake = sigmoid(Wg2*h_g + bg2);

    h_d_fake = tanh_f(Wd1*x_fake + bd1);
    a_fake = Wd2*h_d_fake + bd2;
    y_fake = sigmoid(a_fake);

    % Generator wants D to output REAL
    dA_g = (y_fake - real_label);

    back_d = (Wd2'*dA_g) .* d_tanh(h_d_fake);
    dx = (Wd1'*back_d) .* d_sigmoid(x_fake);

    dWg2 = (dx*h_g') / batch_size;
    dbg2 = mean(dx,2);

    t_g = (Wg2'*dx) .* d_tanh(h_g);
    dWg1 = (t_g*z') / batch_size;
    dbg1 = mean(t_g,2);

    % Update G
    Wg1 = Wg1 - lr_G*dWg1;
    bg1 = bg1 - lr_G*dbg1;
    Wg2 = Wg2 - lr_G*dWg2;
    bg2 = bg2 - lr_G*dbg2;

    %% -------- Logging --------
    loss_D = -mean(log(y_real+1e-8) + log(1-y_fake+1e-8));
    loss_G = -mean(log(y_fake+1e-8));

    loss_G_log = [loss_G_log loss_G];
    loss_D_log = [loss_D_log loss_D];

end

%% =========================================================
%  5. EXPORT WEIGHTS (FORMAT SAMA)
%% =========================================================
fprintf('Exporting weights...\n');

T=Wg1'; dlmwrite('raw_Wg1.txt',T(:),' ');
dlmwrite('raw_bg1.txt',bg1(:),' ');
T=Wg2'; dlmwrite('raw_Wg2.txt',T(:),' ');
dlmwrite('raw_bg2.txt',bg2(:),' ');

T=Wd1'; dlmwrite('raw_Wd1.txt',T(:),' ');
dlmwrite('raw_bd1.txt',bd1(:),' ');
T=Wd2'; dlmwrite('raw_Wd2.txt',T(:),' ');
dlmwrite('raw_bd2.txt',bd2(:),' ');

z_test = randn(2,5);
dlmwrite('raw_input_z.txt',z_test(:),' ');

fprintf('SUCCESS\n');

%% =========================================================
%  6. LOSS PLOT
%% =========================================================
figure;
plot(loss_G_log,'b','LineWidth',1.2); hold on;
plot(loss_D_log,'r','LineWidth',1.2);
legend('Generator','Discriminator');
title('SimpleGAN Improved Training');
grid on;
