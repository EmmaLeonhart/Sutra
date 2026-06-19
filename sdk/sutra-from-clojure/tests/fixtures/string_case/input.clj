(defn classify [s] (case s "foo" 10 "bar" 20 30))
(defn main [] (+ (+ (classify "foo") (classify "bar")) (classify "baz")))
