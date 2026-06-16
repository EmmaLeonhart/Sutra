(defn sum2 [p]
  (+ (get p 1) (get p 2)))

(defn main []
  (sum2 {1 5 2 8}))
