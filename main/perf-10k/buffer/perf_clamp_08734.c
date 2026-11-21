/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_08734(unsigned int count)
{
    const unsigned int limit = 82u;
    return count > limit ? limit : count;
}
