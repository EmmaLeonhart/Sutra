(defn sum2 [p]
  (+ (get p :x) (get p :y)))

(defn main []
  (sum2 {"x" 6 "y" 7}))
