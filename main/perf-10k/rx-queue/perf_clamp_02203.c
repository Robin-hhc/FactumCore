/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_02203(unsigned int count)
{
    const unsigned int limit = 109u;
    return count > limit ? limit : count;
}
