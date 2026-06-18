(defn f [t]
  (let [[[a b] c] t]
    (+ (+ a b) c)))

(defn main [] (f [[5 8] 3]))
