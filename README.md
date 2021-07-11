# WaveFunctionCollapse
![img](https://github.com/sansansan-333/WaveFunctionCollapse/blob/main/image_sample.png?raw=true)

本家 https://github.com/mxgmn/WaveFunctionCollapse

overlapping modelの実装  
入力画像からそれに似た出力画像をランダムで生成する  

## 使い方
```
wfc = WFC(~~~~~)  
wfc.do_magic()
```

## WFCクラスについて  
- コンストラクタ  
    - image_path: 入力画像のパス。16x16くらいの画像が無難。大きすぎると死ぬまで待つことになる
    - extract_size: patternサイズ（rotateがfalseなら正方形以外も可）
    - output_size: 出力画像のサイズ。大きすぎると死ぬまで待つことになる
    - rotate: 抜き出したpatternを回転させたものもまたpatternとして扱うかのフラグ。falseだと出力が入力により似る
    - diagnal_check: patternのconstrainにコーナーの外側（合わせて４つ）を含めるかのフラグ。trueにすると出力がより入力っぽくなるがcontradictionが起きやすくなる

# 参考にしたもの
very simple explanation https://robertheaton.com/2018/12/17/wavefunction-collapse-algorithm/

3dに応用 https://github.com/marian42/wavefunctioncollapse

アルゴリズムの簡単な流れ https://creativecoding.soe.ucsc.edu/courses/cmpm202_w20/slides/W2_Tues_Karth_WaveFunctionCollapse.pdf

pythonでの説明 https://medium.com/swlh/wave-function-collapse-tutorial-with-a-basic-exmaple-implementation-in-python-152d83d5cdb1

paper https://adamsmith.as/papers/wfc_is_constraint_solving_in_the_wild.pdf

アニメで説明 http://oskarstalberg.com/game/wave/wave.html

twitter 画像付きで説明 https://twitter.com/exppad/status/1267045322116734977

youtube わかりやすい https://www.youtube.com/watch?v=2SuvO4Gi7uY&feature=youtu.be


# 今後
速くなってほしい  
コードがきれいになってほしい  
せめてシェルかなんかにしとく  



