/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_02904(unsigned int count)
{
    const unsigned int limit = 74u;
    return count > limit ? limit : count;
}
