/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_02862(unsigned int count)
{
    const unsigned int limit = 107u;
    return count > limit ? limit : count;
}
