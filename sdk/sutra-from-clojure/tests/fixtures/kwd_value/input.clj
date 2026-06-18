(defn classify [k] (if (= k :foo) 10 20))
(defn main [] (+ (classify :foo) (classify :bar)))
