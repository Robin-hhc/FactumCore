/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_06270(unsigned int count)
{
    const unsigned int limit = 26u;
    return count > limit ? limit : count;
}
